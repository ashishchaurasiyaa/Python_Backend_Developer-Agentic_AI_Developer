# FastAPI — Function Calling / Tool Use Endpoints
**Phase 2 FastAPI | Senior Backend + Agentic AI**

## Quick Concepts
- **Function calling** = LLM ko aapke functions/APIs call karne dena (tool use)
- **Tool schema** = JSON schema describing function name, params, types
- **Tool execution loop** = LLM picks tool → backend runs it → result back to LLM → final answer
- **Parallel tool use** = LLM can call multiple tools at once (Claude/GPT-4o support karte hain)
- **Structured output** = LLM returns Pydantic-validated JSON instead of free text
- **Tool registry** = central dict of `name → callable` for routing

---

## Architecture

```
User Query
    ↓
FastAPI endpoint → LLM (with tools list)
    ↓
LLM decides → "use tool X with args Y"
    ↓
Backend executes tool X(Y) → result
    ↓
Send result back to LLM
    ↓
LLM → final user-facing answer
```

---

## Interview Questions & Answers

### Q1: Tool registry pattern with Pydantic schemas?

**Answer:** Centralized registry — LLM tools = your API functions wrapped.

```python
import inspect
from typing import Any, Callable, get_type_hints
from pydantic import BaseModel, Field, create_model

# ─── Tool registry ───
class Tool(BaseModel):
    name: str
    description: str
    parameters: dict  # JSON schema
    handler: Callable

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, name: str, description: str):
        """Decorator to register a function as an LLM tool."""
        def decorator(fn: Callable):
            # Auto-generate JSON schema from function signature
            sig = inspect.signature(fn)
            hints = get_type_hints(fn)
            fields = {}
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                annotation = hints.get(param_name, str)
                default = param.default if param.default is not inspect.Parameter.empty else ...
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

    def get_anthropic_schema(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in self._tools.values()
        ]

    def get_openai_schema(self) -> list[dict]:
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

    async def execute(self, name: str, args: dict) -> Any:
        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")
        handler = self._tools[name].handler
        if inspect.iscoroutinefunction(handler):
            return await handler(**args)
        return handler(**args)

registry = ToolRegistry()
```

---

### Q2: Real tools registered (weather, DB query, calculator)?

**Answer:** Register backend functions as tools.

```python
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

# ─── Tool 1: Weather API ───
@registry.register(
    name="get_weather",
    description="Get current weather for a city. Use when user asks about weather.",
)
async def get_weather(city: str, units: str = "celsius") -> dict:
    """
    Args:
        city: City name (e.g., 'Mumbai', 'Delhi')
        units: Temperature units ('celsius' or 'fahrenheit')
    """
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"https://api.weatherapi.com/v1/current.json",
            params={"q": city, "key": "YOUR_KEY"},
        )
        data = resp.json()
        temp = data["current"]["temp_c"] if units == "celsius" else data["current"]["temp_f"]
        return {
            "city": city,
            "temperature": temp,
            "units": units,
            "condition": data["current"]["condition"]["text"],
        }

# ─── Tool 2: Database lookup ───
@registry.register(
    name="get_user_orders",
    description="Fetch order history for a user by user_id. Returns list of orders.",
)
async def get_user_orders(user_id: int, limit: int = 10) -> list[dict]:
    from app.db import async_session
    async with async_session() as session:
        result = await session.execute(
            "SELECT id, total, status, created_at FROM orders WHERE user_id = :uid ORDER BY created_at DESC LIMIT :lim",
            {"uid": user_id, "lim": limit},
        )
        return [dict(r._mapping) for r in result.all()]

# ─── Tool 3: Calculator (safe eval) ───
@registry.register(
    name="calculator",
    description="Evaluate math expression. Supports +, -, *, /, **, parens.",
)
def calculator(expression: str) -> float:
    import ast
    import operator
    OPS = {
        ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg,
    }
    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp):
            return OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            return OPS[type(node.op)](_eval(node.operand))
        raise ValueError("Unsafe expression")
    tree = ast.parse(expression, mode="eval")
    return _eval(tree.body)
```

⚠️ **Never use `eval()`** for LLM-generated math. Use AST whitelist (above) or `simpleeval` library.

---

### Q3: Tool execution loop with Claude?

**Answer:** Multi-turn loop until LLM stops requesting tools.

```python
from anthropic import AsyncAnthropic

client = AsyncAnthropic()

MAX_ITERATIONS = 10  # safety: prevent infinite loops

async def chat_with_tools(user_message: str) -> str:
    messages = [{"role": "user", "content": user_message}]

    for iteration in range(MAX_ITERATIONS):
        response = await client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            tools=registry.get_anthropic_schema(),
            messages=messages,
        )

        # LLM finished (no more tool calls)
        if response.stop_reason == "end_turn":
            return response.content[0].text

        # LLM wants to use tools
        if response.stop_reason == "tool_use":
            # Add assistant message to history
            messages.append({"role": "assistant", "content": response.content})

            # Execute all tool calls (parallel)
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        result = await registry.execute(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })
                    except Exception as e:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Error: {e}",
                            "is_error": True,
                        })

            messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop reason
        break

    raise RuntimeError(f"Tool loop exceeded {MAX_ITERATIONS} iterations")
```

---

### Q4: FastAPI endpoint for tool-use chat?

**Answer:**
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class ToolChatRequest(BaseModel):
    message: str
    allowed_tools: list[str] | None = None  # restrict tools per request

class ToolChatResponse(BaseModel):
    answer: str
    tools_used: list[str]
    iterations: int

@app.post("/chat/tools", response_model=ToolChatResponse)
async def chat_tools(req: ToolChatRequest):
    # Filter allowed tools
    available = registry.get_anthropic_schema()
    if req.allowed_tools:
        available = [t for t in available if t["name"] in req.allowed_tools]

    messages = [{"role": "user", "content": req.message}]
    tools_used = []
    iterations = 0

    for iteration in range(10):
        iterations += 1
        response = await client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            tools=available,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            text = "".join(b.text for b in response.content if b.type == "text")
            return ToolChatResponse(
                answer=text,
                tools_used=tools_used,
                iterations=iterations,
            )

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tools_used.append(block.name)
                    try:
                        result = await registry.execute(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })
                    except Exception as e:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": f"Error: {e}",
                            "is_error": True,
                        })
            messages.append({"role": "user", "content": tool_results})

    raise HTTPException(status_code=500, detail="Tool loop too long")
```

---

### Q5: Structured output (Pydantic-validated JSON) without tool loop?

**Answer:** Force LLM to return validated structure — no free text.

```python
from anthropic import AsyncAnthropic
from pydantic import BaseModel, ValidationError

class OrderExtraction(BaseModel):
    customer_name: str
    items: list[str]
    total_amount: float
    payment_method: str

@app.post("/extract/order")
async def extract_order(text: str):
    """Extract structured order from natural language."""
    response = await client.messages.create(
        model="claude-opus-4-7",
        max_tokens=1024,
        tools=[{
            "name": "extract_order",
            "description": "Extract order details from text",
            "input_schema": OrderExtraction.model_json_schema(),
        }],
        tool_choice={"type": "tool", "name": "extract_order"},  # force this tool
        messages=[{"role": "user", "content": text}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_order":
            try:
                return OrderExtraction.model_validate(block.input)
            except ValidationError as e:
                raise HTTPException(400, f"Invalid extraction: {e}")

    raise HTTPException(500, "No structured output returned")
```

**Alternative: `instructor` library** (Pydantic-first):
```python
import instructor
from openai import AsyncOpenAI

client = instructor.from_openai(AsyncOpenAI())

@app.post("/extract/v2")
async def extract_v2(text: str) -> OrderExtraction:
    return await client.chat.completions.create(
        model="gpt-4o",
        response_model=OrderExtraction,
        messages=[{"role": "user", "content": text}],
        max_retries=2,  # auto-retry on validation failure
    )
```

---

### Q6: Parallel tool calls (multiple tools in one turn)?

**Answer:** Claude/GPT-4o natively support — execute all in parallel with `asyncio.gather`.

```python
import asyncio

async def execute_tools_parallel(tool_calls: list) -> list[dict]:
    """Execute multiple tool calls concurrently."""
    async def _run(call):
        try:
            result = await registry.execute(call.name, call.input)
            return {
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": str(result),
            }
        except Exception as e:
            return {
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": f"Error: {e}",
                "is_error": True,
            }

    return await asyncio.gather(*[_run(c) for c in tool_calls])

# In the loop:
if response.stop_reason == "tool_use":
    tool_calls = [b for b in response.content if b.type == "tool_use"]
    tool_results = await execute_tools_parallel(tool_calls)
    messages.append({"role": "user", "content": tool_results})
```

**Example LLM thinking:** "User asks for weather in Mumbai AND order history" → LLM calls `get_weather("Mumbai")` and `get_user_orders(123)` simultaneously → both execute in parallel → both results returned.

---

### Q7: Tool authorization (per-user permissions)?

**Answer:** Don't trust LLM — enforce auth at tool execution layer.

```python
from fastapi import Depends

class ToolContext(BaseModel):
    user_id: int
    role: str
    permissions: set[str]

async def get_tool_context(user_id: int = Depends(get_current_user_id)) -> ToolContext:
    # Load from DB
    user = await load_user(user_id)
    return ToolContext(
        user_id=user.id,
        role=user.role,
        permissions=set(user.permissions),
    )

# ─── Permission-aware tool ───
@registry.register(
    name="delete_user_data",
    description="Delete a user's data (admin only)",
)
async def delete_user_data(target_user_id: int, ctx: ToolContext = None) -> dict:
    if not ctx or "admin" not in ctx.permissions:
        return {"error": "Permission denied"}
    # ... actual deletion
    return {"deleted": True}

# ─── Filter tools per user ───
def tools_for_user(ctx: ToolContext) -> list[dict]:
    all_tools = registry.get_anthropic_schema()
    allowed = {
        "viewer": {"get_weather", "calculator"},
        "user": {"get_weather", "calculator", "get_user_orders"},
        "admin": set(t["name"] for t in all_tools),  # all
    }
    permitted = allowed.get(ctx.role, set())
    return [t for t in all_tools if t["name"] in permitted]

@app.post("/chat/tools/secure")
async def chat_secure(
    req: ToolChatRequest,
    ctx: ToolContext = Depends(get_tool_context),
):
    available_tools = tools_for_user(ctx)
    # ... loop with restricted tools
```

---

### Q8: Tool error handling (LLM should self-correct)?

**Answer:** Return errors as `tool_result` with `is_error: True` — LLM will retry or apologize.

```python
async def safe_execute(call) -> dict:
    try:
        result = await asyncio.wait_for(
            registry.execute(call.name, call.input),
            timeout=15.0,  # per-tool timeout
        )
        return {
            "type": "tool_result",
            "tool_use_id": call.id,
            "content": str(result),
        }
    except asyncio.TimeoutError:
        return {
            "type": "tool_result",
            "tool_use_id": call.id,
            "content": f"Tool '{call.name}' timed out after 15s. Try a different approach.",
            "is_error": True,
        }
    except ValueError as e:
        return {
            "type": "tool_result",
            "tool_use_id": call.id,
            "content": f"Invalid arguments: {e}. Please check the parameters and retry.",
            "is_error": True,
        }
    except Exception as e:
        # Log unexpected error
        logger.exception(f"Tool {call.name} crashed")
        return {
            "type": "tool_result",
            "tool_use_id": call.id,
            "content": f"Tool failed unexpectedly. Please inform the user.",
            "is_error": True,
        }
```

---

## Production Patterns

| Pattern | Why |
|---|---|
| **Tool timeout** | LLMs can pick slow tools — cap at 15-30s |
| **Tool whitelist per route** | Don't expose admin tools to public chat |
| **Tool result truncation** | DB queries can return 10MB — truncate to 5KB |
| **Idempotent tools** | LLM may retry; tools should be safe to re-run |
| **Audit log** | Log every tool call with user_id + args + result |
| **Cost tracking** | Tool calls = more LLM tokens; track per tool |
| **Tool versioning** | Schema changes break old conversations — version them |

---

## Common Gotchas

| Gotcha | Fix |
|---|---|
| LLM hallucinated tool name | Validate name against registry; return error |
| LLM passes wrong arg type | Pydantic validation in tool; return error |
| Infinite tool loop | `MAX_ITERATIONS = 10`, log if hit |
| Tool returns huge data | Truncate + summarize before sending to LLM |
| User exploits tool to access others' data | Pass `ctx` with user_id; enforce in tool |
| Tool calls external API and fails | Wrap in try/except; return `is_error: True` |
| Sensitive data in tool result | Sanitize (PII redaction) before sending to LLM |

---

## Senior-level Checklist

- [ ] Centralized tool registry with auto-generated schemas
- [ ] Per-tool timeout (15-30s default)
- [ ] User-based tool authorization (RBAC)
- [ ] Tool result truncation (max 5KB)
- [ ] `is_error: True` for failures (let LLM self-correct)
- [ ] Max iterations safety (10)
- [ ] Parallel tool execution via `asyncio.gather`
- [ ] Audit logging (user_id, tool, args, result, latency)
- [ ] Tool cost tracking
- [ ] Structured output via `tool_choice` forcing

---

## Related Docs
- `31_llm_integration_fastapi.md` — base LLM integration
- `33_prompt_injection_security.md` — securing tool inputs
- `35_mcp_server_implementation.md` — tools as MCP servers
- `Phase3_Security/01_jwt_oauth2_rbac.md` — auth for tool access
