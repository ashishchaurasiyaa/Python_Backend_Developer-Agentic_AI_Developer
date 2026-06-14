"""
FastAPI — Function Calling / Tool Use Endpoints

Covers the full senior-level pattern for exposing backend functions as LLM tools:

    1.  ToolRegistry — auto-generate JSON schemas from Python type hints
    2.  Real tool implementations — weather stub, safe calculator, order lookup stub
    3.  Tool execution loop with Claude (Anthropic SDK)
    4.  FastAPI endpoints: /chat/tools, /chat/tools/secure, /extract/order
    5.  Parallel tool execution via asyncio.gather
    6.  Per-tool timeout + structured error results (is_error: True)
    7.  RBAC — role-based tool filtering, per-user ToolContext
    8.  Tool result truncation (max 5 KB)
    9.  Audit logging decorator
    10. Structured output forcing via tool_choice

Run (syntax + imports check only — no LLM key or DB required):
    python -m py_compile 32_function_calling_endpoints.py && echo OK

Run the server (requires pip installs below):
    uvicorn 32_function_calling_endpoints:app --reload
"""

# pip install fastapi uvicorn anthropic httpx pydantic structlog

from __future__ import annotations

import ast
import asyncio
import inspect
import logging
import operator
import time
from functools import wraps
from typing import Any, Callable, List, Optional, Set, get_type_hints

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError, create_model

# ==========================================================================
# 1. LOGGING
# ==========================================================================

log = structlog.get_logger()
logger = logging.getLogger(__name__)


# ==========================================================================
# 2. TOOL REGISTRY
# ==========================================================================

class Tool(BaseModel):
    """Metadata for a single registered tool."""

    name: str
    description: str
    parameters: dict          # JSON Schema understood by both Anthropic and OpenAI
    handler: Any              # Callable — excluded from model serialization

    model_config: Any = {"arbitrary_types_allowed": True}


class ToolRegistry:
    """
    Central registry that maps tool names to callables and their JSON schemas.

    Usage:
        registry = ToolRegistry()

        @registry.register(name="my_tool", description="Does X")
        async def my_tool(param: str) -> dict: ...
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, name: str, description: str) -> Callable:
        """Decorator — introspects function signature and auto-builds JSON schema."""
        def decorator(fn: Callable) -> Callable:
            sig = inspect.signature(fn)
            hints = get_type_hints(fn)
            fields: dict[str, Any] = {}

            for param_name, param in sig.parameters.items():
                if param_name in ("self", "ctx"):   # skip injected context
                    continue
                annotation = hints.get(param_name, str)
                default = (
                    param.default
                    if param.default is not inspect.Parameter.empty
                    else ...
                )
                fields[param_name] = (annotation, Field(default))

            ParamModel = create_model(f"{name}_params", **fields)

            self._tools[name] = Tool(
                name=name,
                description=description,
                parameters=ParamModel.model_json_schema(),
                handler=fn,
            )
            return fn

        return decorator

    # ------------------------------------------------------------------
    # Schema export helpers
    # ------------------------------------------------------------------

    def get_anthropic_schema(self) -> List[dict]:
        """Return tools list in Anthropic (Claude) format."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in self._tools.values()
        ]

    def get_openai_schema(self) -> List[dict]:
        """Return tools list in OpenAI (GPT-4o) format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(self, name: str, args: dict) -> Any:
        """Dispatch a tool call — supports both sync and async handlers."""
        if name not in self._tools:
            raise ValueError(f"Unknown tool: '{name}'. Available: {self.names()}")
        handler = self._tools[name].handler
        if inspect.iscoroutinefunction(handler):
            return await handler(**args)
        return handler(**args)


# Module-level singleton shared by all endpoints
registry = ToolRegistry()


# ==========================================================================
# 3. TOOL IMPLEMENTATIONS
# ==========================================================================

# --------------------------------------------------------------------------
# Tool 1: Weather (stubbed — replace httpx call with real API key in prod)
# --------------------------------------------------------------------------

@registry.register(
    name="get_weather",
    description=(
        "Get current weather for a city. Use when the user asks about temperature, "
        "rain, or weather conditions in a specific location."
    ),
)
async def get_weather(city: str, units: str = "celsius") -> dict:
    """
    Args:
        city:  City name, e.g. 'Mumbai', 'London'.
        units: 'celsius' or 'fahrenheit'.
    """
    # pip install httpx
    # In production, replace this stub with a real weather API call:
    #
    #   async with httpx.AsyncClient(timeout=10) as client:
    #       resp = await client.get(
    #           "https://api.weatherapi.com/v1/current.json",
    #           params={"q": city, "key": "YOUR_WEATHERAPI_KEY"},
    #       )
    #       data = resp.json()
    #       temp = data["current"]["temp_c" if units == "celsius" else "temp_f"]
    #       return {"city": city, "temperature": temp, "units": units,
    #               "condition": data["current"]["condition"]["text"]}

    # Stub: returns plausible fake data so the module can run without a key
    stub_data = {
        "city": city,
        "temperature": 28.5 if units == "celsius" else 83.3,
        "units": units,
        "condition": "Partly cloudy",
        "source": "stub",
    }
    return stub_data


# --------------------------------------------------------------------------
# Tool 2: Safe calculator (AST whitelist — never use eval() with LLM input)
# --------------------------------------------------------------------------

_SAFE_OPS: dict[type, Callable] = {
    ast.Add:  operator.add,
    ast.Sub:  operator.sub,
    ast.Mult: operator.mul,
    ast.Div:  operator.truediv,
    ast.Pow:  operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node: ast.AST) -> float:
    """Recursively evaluate a whitelisted AST node."""
    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)):
            raise ValueError(f"Non-numeric constant: {node.value!r}")
        return float(node.value)
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        return _SAFE_OPS[op_type](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        return _SAFE_OPS[op_type](_safe_eval(node.operand))
    raise ValueError(f"Unsafe AST node: {type(node).__name__}")


@registry.register(
    name="calculator",
    description=(
        "Safely evaluate a math expression. Supports +, -, *, /, **, "
        "parentheses, and integer/float literals. Do NOT use for anything "
        "other than arithmetic."
    ),
)
def calculator(expression: str) -> float:
    """
    Args:
        expression: Math expression string, e.g. '(3 + 4) * 2 ** 3'.
    """
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        return _safe_eval(tree.body)
    except (SyntaxError, ValueError) as exc:
        raise ValueError(f"Invalid expression '{expression}': {exc}") from exc


# --------------------------------------------------------------------------
# Tool 3: Order lookup (stubbed — replace with real async DB session in prod)
# --------------------------------------------------------------------------

@registry.register(
    name="get_user_orders",
    description=(
        "Fetch the recent order history for a user by their user_id. "
        "Returns a list of orders including id, total, and status."
    ),
)
async def get_user_orders(user_id: int, limit: int = 10) -> List[dict]:
    """
    Args:
        user_id: Integer user identifier.
        limit:   Maximum number of orders to return (default 10).

    In production replace with:

        from app.db import async_session
        async with async_session() as session:
            result = await session.execute(
                "SELECT id, total, status, created_at "
                "FROM orders WHERE user_id = :uid "
                "ORDER BY created_at DESC LIMIT :lim",
                {"uid": user_id, "lim": limit},
            )
            return [dict(r._mapping) for r in result.all()]
    """
    # Stub: returns fake orders so the module is self-contained
    stub_orders = [
        {"id": 1001 + i, "total": round(49.99 + i * 10, 2), "status": "delivered"}
        for i in range(min(limit, 3))
    ]
    return stub_orders


# ==========================================================================
# 4. TOOL AUTHORIZATION — RBAC
# ==========================================================================

class ToolContext(BaseModel):
    """Injected per-request; carries the authenticated user's identity."""

    user_id: int
    role: str                    # 'viewer' | 'user' | 'admin'
    permissions: Set[str]

    model_config: Any = {"arbitrary_types_allowed": True}


# Role-to-allowed-tools mapping (extend as needed)
_ROLE_TOOL_WHITELIST: dict = {
    "viewer": {"get_weather", "calculator"},
    "user":   {"get_weather", "calculator", "get_user_orders"},
    "admin":  set(registry.names()),   # all tools
}


def tools_for_user(ctx: ToolContext) -> List[dict]:
    """Return the Anthropic-format tool schemas the user's role permits."""
    permitted = _ROLE_TOOL_WHITELIST.get(ctx.role, set())
    return [t for t in registry.get_anthropic_schema() if t["name"] in permitted]


# --------------------------------------------------------------------------
# FastAPI dependency — normally reads a JWT; here returns a stub context
# --------------------------------------------------------------------------

async def get_tool_context(
    request: Request,
) -> ToolContext:
    """
    In production, decode a Bearer JWT and load the user from the DB:

        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user = await load_user(payload["sub"])
        return ToolContext(user_id=user.id, role=user.role,
                           permissions=set(user.permissions))
    """
    # Stub: grant 'user' role to all callers so the demo endpoint is testable
    return ToolContext(user_id=1, role="user", permissions={"get_user_orders"})


# ==========================================================================
# 5. TOOL RESULT UTILITIES
# ==========================================================================

_MAX_RESULT_BYTES = 5_120   # 5 KB — keep LLM context window lean


def truncate_result(result: Any) -> str:
    """
    Serialize a tool result to string and truncate to _MAX_RESULT_BYTES.
    Prevents huge DB dumps or API responses from flooding the LLM context.
    """
    text = str(result)
    if len(text.encode()) > _MAX_RESULT_BYTES:
        truncated = text.encode()[:_MAX_RESULT_BYTES].decode(errors="ignore")
        return truncated + "\n... [truncated — result exceeded 5 KB]"
    return text


# ==========================================================================
# 6. SAFE TOOL EXECUTION (timeout + structured error)
# ==========================================================================

_TOOL_TIMEOUT_SECONDS = 15.0


async def safe_execute(name: str, args: dict, tool_use_id: str) -> dict:
    """
    Run a tool with a per-call timeout.  On any failure, return a structured
    error result so the LLM can self-correct rather than crashing the loop.
    """
    try:
        result = await asyncio.wait_for(
            registry.execute(name, args),
            timeout=_TOOL_TIMEOUT_SECONDS,
        )
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": truncate_result(result),
        }
    except asyncio.TimeoutError:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": (
                f"Tool '{name}' timed out after {_TOOL_TIMEOUT_SECONDS}s. "
                "Try a different approach or reduce the scope of your request."
            ),
            "is_error": True,
        }
    except ValueError as exc:
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": f"Invalid arguments for '{name}': {exc}. Please check the parameters and retry.",
            "is_error": True,
        }
    except Exception as exc:
        logger.exception("Tool '%s' crashed with args %s", name, args)
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": "Tool failed unexpectedly. Please inform the user and try an alternative.",
            "is_error": True,
        }


# ==========================================================================
# 7. PARALLEL TOOL EXECUTION
# ==========================================================================

async def execute_tools_parallel(tool_calls: list) -> List[dict]:
    """
    Execute all tool calls from a single LLM turn concurrently.

    Claude (and GPT-4o) can request multiple tools in one response.
    Running them in parallel reduces wall-clock latency significantly.
    """
    tasks = [
        safe_execute(call.name, call.input, call.id)
        for call in tool_calls
    ]
    return await asyncio.gather(*tasks)


# ==========================================================================
# 8. AUDIT LOGGING DECORATOR
# ==========================================================================

def audit_tool_call(fn: Callable) -> Callable:
    """
    Decorator that logs every tool execution to the structured logger,
    including user_id, tool name, args, result summary, and latency.
    Essential for compliance (GDPR / SOC 2) and cost tracking.
    """
    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        try:
            result = await fn(*args, **kwargs)
            latency_ms = int((time.monotonic() - start) * 1000)
            log.info(
                "tool_call_success",
                tool=fn.__name__,
                latency_ms=latency_ms,
                args=kwargs,
            )
            return result
        except Exception:
            latency_ms = int((time.monotonic() - start) * 1000)
            log.error(
                "tool_call_failed",
                tool=fn.__name__,
                latency_ms=latency_ms,
                args=kwargs,
            )
            raise
    return wrapper


# ==========================================================================
# 9. ANTHROPIC CLIENT
# ==========================================================================

# pip install anthropic
try:
    from anthropic import AsyncAnthropic
    _anthropic_client: Optional[AsyncAnthropic] = AsyncAnthropic()
except ImportError:
    _anthropic_client = None

_LLM_MODEL = "claude-opus-4-5"
_MAX_TOKENS = 4096
_MAX_ITERATIONS = 10   # safety cap — prevents runaway tool loops


# ==========================================================================
# 10. CORE TOOL LOOP
# ==========================================================================

async def chat_with_tools(
    user_message: str,
    allowed_tools: Optional[List[dict]] = None,
) -> tuple:
    """
    Drive the LLM tool-use loop until stop_reason == 'end_turn'.

    Returns:
        (final_answer_text, list_of_tool_names_used, iteration_count)

    The loop is:
        1. Send message + tools to LLM.
        2. If LLM responds with end_turn → return text.
        3. If LLM responds with tool_use → execute tools (parallel), append
           results, go to step 1.
        4. After MAX_ITERATIONS raise RuntimeError.
    """
    if _anthropic_client is None:
        raise RuntimeError("anthropic package not installed — pip install anthropic")

    tools = allowed_tools if allowed_tools is not None else registry.get_anthropic_schema()
    messages: list[dict] = [{"role": "user", "content": user_message}]
    tools_used: list[str] = []

    for iteration in range(1, _MAX_ITERATIONS + 1):
        response = await _anthropic_client.messages.create(
            model=_LLM_MODEL,
            max_tokens=_MAX_TOKENS,
            tools=tools,
            messages=messages,
        )

        # LLM finished — extract and return text
        if response.stop_reason == "end_turn":
            text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            return text, tools_used, iteration

        # LLM wants to call tools
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_calls = [b for b in response.content if b.type == "tool_use"]
            tools_used.extend(call.name for call in tool_calls)

            # Execute all tool calls in parallel
            tool_results = await execute_tools_parallel(tool_calls)
            messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop reason (max_tokens, stop_sequence, etc.)
        log.warning("unexpected_stop_reason", stop_reason=response.stop_reason)
        break

    raise RuntimeError(
        f"Tool loop exceeded {_MAX_ITERATIONS} iterations — possible runaway cycle."
    )


# ==========================================================================
# 11. FASTAPI APPLICATION
# ==========================================================================

app = FastAPI(
    title="Function Calling / Tool Use Endpoints",
    description=(
        "Demonstrates LLM function calling over FastAPI: "
        "tool registry, execution loop, RBAC, structured output."
    ),
    version="1.0.0",
)


# ==========================================================================
# 12. REQUEST / RESPONSE SCHEMAS
# ==========================================================================

class ToolChatRequest(BaseModel):
    message: str = Field(..., description="User message / natural language query.")
    allowed_tools: Optional[List[str]] = Field(
        default=None,
        description="Optional whitelist of tool names for this request. "
                    "Leave null to allow all registered tools.",
    )


class ToolChatResponse(BaseModel):
    answer: str
    tools_used: List[str]
    iterations: int


class OrderExtraction(BaseModel):
    """Pydantic schema used to force-extract a structured order from free text."""

    customer_name: str
    items: List[str]
    total_amount: float
    payment_method: str


class OrderExtractionRequest(BaseModel):
    text: str = Field(..., description="Free-form text describing an order.")


# ==========================================================================
# 13. ENDPOINTS
# ==========================================================================

# --------------------------------------------------------------------------
# POST /chat/tools — public tool-use chat (no auth)
# --------------------------------------------------------------------------

@app.post("/chat/tools", response_model=ToolChatResponse, tags=["Chat"])
async def chat_tools(req: ToolChatRequest) -> ToolChatResponse:
    """
    Send a message to Claude with access to the registered tool suite.
    The loop continues until Claude stops requesting tools.

    - Optionally restrict tool access via `allowed_tools`.
    - Requires ANTHROPIC_API_KEY environment variable.
    """
    available = registry.get_anthropic_schema()
    if req.allowed_tools:
        available = [t for t in available if t["name"] in req.allowed_tools]

    try:
        answer, tools_used, iterations = await chat_with_tools(
            user_message=req.message,
            allowed_tools=available,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ToolChatResponse(
        answer=answer,
        tools_used=tools_used,
        iterations=iterations,
    )


# --------------------------------------------------------------------------
# POST /chat/tools/secure — RBAC-protected endpoint
# --------------------------------------------------------------------------

@app.post("/chat/tools/secure", response_model=ToolChatResponse, tags=["Chat"])
async def chat_tools_secure(
    req: ToolChatRequest,
    ctx: ToolContext = Depends(get_tool_context),
) -> ToolChatResponse:
    """
    Role-based tool access: the caller's role (injected via JWT in prod)
    determines which tools are exposed to the LLM for this session.

    - viewer  → get_weather, calculator
    - user    → + get_user_orders
    - admin   → all tools
    """
    available = tools_for_user(ctx)

    # If caller supplied an explicit allowlist, intersect with role permissions
    if req.allowed_tools:
        allowed_names = set(req.allowed_tools)
        available = [t for t in available if t["name"] in allowed_names]

    log.info(
        "secure_chat_request",
        user_id=ctx.user_id,
        role=ctx.role,
        available_tools=[t["name"] for t in available],
    )

    try:
        answer, tools_used, iterations = await chat_with_tools(
            user_message=req.message,
            allowed_tools=available,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ToolChatResponse(
        answer=answer,
        tools_used=tools_used,
        iterations=iterations,
    )


# --------------------------------------------------------------------------
# POST /extract/order — structured output via forced tool_choice
# --------------------------------------------------------------------------

@app.post("/extract/order", response_model=OrderExtraction, tags=["Extraction"])
async def extract_order(req: OrderExtractionRequest) -> OrderExtraction:
    """
    Force the LLM to populate a Pydantic model (OrderExtraction) from
    unstructured text. Uses tool_choice={'type':'tool','name':'extract_order'}
    to guarantee structured output — no free-text fallback.

    Example input:
        "John ordered 2x Butter Chicken and 1x Garlic Naan, total Rs 450, paid by UPI."
    """
    if _anthropic_client is None:
        raise HTTPException(status_code=503, detail="anthropic not installed")

    extraction_tool = {
        "name": "extract_order",
        "description": "Extract structured order details from natural language text.",
        "input_schema": OrderExtraction.model_json_schema(),
    }

    response = await _anthropic_client.messages.create(
        model=_LLM_MODEL,
        max_tokens=1024,
        tools=[extraction_tool],
        tool_choice={"type": "tool", "name": "extract_order"},   # force this tool
        messages=[{"role": "user", "content": req.text}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_order":
            try:
                return OrderExtraction.model_validate(block.input)
            except ValidationError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=f"LLM returned invalid structure: {exc}",
                ) from exc

    raise HTTPException(status_code=500, detail="No structured output returned by LLM.")


# --------------------------------------------------------------------------
# GET /tools — introspection endpoint (dev / monitoring)
# --------------------------------------------------------------------------

@app.get("/tools", tags=["Meta"])
async def list_tools() -> dict:
    """Return the full Anthropic-format schema for all registered tools."""
    return {
        "count": len(registry.names()),
        "tools": registry.get_anthropic_schema(),
    }


# --------------------------------------------------------------------------
# GET /health
# --------------------------------------------------------------------------

@app.get("/health", tags=["Meta"])
async def health() -> dict:
    return {"status": "ok"}


# ==========================================================================
# 14. PRODUCTION PATTERNS — REFERENCE NOTES
# ==========================================================================

_PRODUCTION_CHECKLIST = """
SENIOR-LEVEL CHECKLIST
======================
[x] Centralized ToolRegistry with auto-generated JSON schemas
[x] Per-tool timeout (15 s default via asyncio.wait_for)
[x] User-based tool authorization (RBAC via ToolContext)
[x] Tool result truncation (max 5 KB via truncate_result)
[x] is_error: True for failures — LLM self-corrects
[x] MAX_ITERATIONS = 10 safety cap
[x] Parallel tool execution via asyncio.gather
[x] Audit logging (tool name, args, latency) via structlog
[x] Structured output via tool_choice forcing
[ ] Tool cost tracking — add token count from response.usage
[ ] Tool versioning — prefix schemas with version: "get_weather_v2"
[ ] PII redaction in tool results before sending to LLM

COMMON GOTCHAS
==============
- Never use eval() for LLM-generated math; use AST whitelist (above).
- Validate tool name against registry before executing — LLM can hallucinate names.
- LLM may retry a failed tool; ensure all tools are idempotent where possible.
- Tool results that contain sensitive data (PII, secrets) must be sanitized.
- Infinite loop guard (MAX_ITERATIONS) is mandatory — not optional.
- Per-user tool filtering must happen at the registry layer, not just in the prompt.

RUN THE SERVER
==============
    pip install fastapi uvicorn anthropic structlog
    export ANTHROPIC_API_KEY=sk-ant-...
    uvicorn 32_function_calling_endpoints:app --reload

EXAMPLE REQUESTS
================
    # Public chat with tool use
    curl -X POST http://localhost:8000/chat/tools \\
         -H 'Content-Type: application/json' \\
         -d '{"message": "What is the weather in Mumbai? Also calculate 37 * 42."}'

    # Structured extraction
    curl -X POST http://localhost:8000/extract/order \\
         -H 'Content-Type: application/json' \\
         -d '{"text": "Alice bought 2x Mango Lassi and 1x Dosa, total Rs 280, paid cash."}'

    # List registered tools
    curl http://localhost:8000/tools
"""


# ==========================================================================
# 15. LOCAL DEMO — runs without LLM key (exercises tool logic only)
# ==========================================================================

if __name__ == "__main__":
    import json

    async def _demo() -> None:
        print("=" * 60)
        print("FUNCTION CALLING ENDPOINTS — LOCAL DEMO (no LLM key)")
        print("=" * 60)

        # --- Tool registry schema ---
        print("\n[1] Registered tool schemas (Anthropic format):")
        schemas = registry.get_anthropic_schema()
        print(json.dumps(schemas, indent=2))

        # --- Calculator tool ---
        print("\n[2] Calculator tool:")
        result = await registry.execute("calculator", {"expression": "(3 + 4) * 2 ** 3"})
        print(f"  (3 + 4) * 2 ** 3 = {result}")

        # --- Weather stub ---
        print("\n[3] Weather stub:")
        weather = await registry.execute("get_weather", {"city": "Mumbai", "units": "celsius"})
        print(f"  {weather}")

        # --- Order lookup stub ---
        print("\n[4] Order lookup stub:")
        orders = await registry.execute("get_user_orders", {"user_id": 42, "limit": 3})
        print(f"  {orders}")

        # --- safe_execute with error ---
        print("\n[5] safe_execute — invalid expression (error path):")
        err_result = await safe_execute(
            name="calculator",
            args={"expression": "import os"},
            tool_use_id="fake-id-001",
        )
        print(f"  {err_result}")

        # --- Truncation ---
        print("\n[6] Result truncation (5 KB cap):")
        big_string = "x" * 10_000
        truncated = truncate_result(big_string)
        print(f"  Input length: {len(big_string)} chars")
        print(f"  Output length: {len(truncated)} chars (truncated: {'...' in truncated})")

        # --- RBAC filtering ---
        print("\n[7] RBAC — tools visible per role:")
        for role in ("viewer", "user", "admin"):
            ctx = ToolContext(user_id=1, role=role, permissions=set())
            visible = [t["name"] for t in tools_for_user(ctx)]
            print(f"  {role:8s} → {visible}")

        # --- OrderExtraction schema ---
        print("\n[8] OrderExtraction JSON schema:")
        print(json.dumps(OrderExtraction.model_json_schema(), indent=2))

        print("\nDemo complete. Start the server to test /chat/tools with a real API key.")

    asyncio.run(_demo())
