"""
Advanced LLM Tool Use / Function Calling — Practical Demos
==========================================================
Python Backend Developer + Agentic AI Interview Prep — 40 LPA Series
File 02 — Tool Use Advanced Practical

Run:
    python 02_tool_use_advanced.py          # Run all demos
    python 02_tool_use_advanced.py demo     # Run all demos (same)
    python 02_tool_use_advanced.py section1 # Tool definitions only
    python 02_tool_use_advanced.py section2 # Tool executor only
    python 02_tool_use_advanced.py section3 # Parallel tools
    python 02_tool_use_advanced.py section4 # Agent loop
    python 02_tool_use_advanced.py section5 # Error recovery
    python 02_tool_use_advanced.py section6 # Pydantic validation
    python 02_tool_use_advanced.py section7 # Security demo

Works WITHOUT API keys (uses mock LLM).
Set OPENAI_API_KEY or ANTHROPIC_API_KEY to use real LLM.

Author: Interview Prep Series
"""

import os
import sys
import json
import time
import random
import asyncio
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Callable

# ──────────────────────────────────────────────
#  Real LLM flag — set automatically from env
# ──────────────────────────────────────────────
USE_REAL_LLM = bool(os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))

if USE_REAL_LLM:
    print("✓ Real LLM mode: API key detected")
else:
    print("ℹ  Mock LLM mode: No API key found — all demos run with simulated LLM")

# ──────────────────────────────────────────────
#  Logging setup
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("tool_use")
audit_logger = logging.getLogger("tool_audit")

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 1 — Tool Definition + JSON Schema + Pydantic Integration
# ══════════════════════════════════════════════════════════════════════════════

try:
    from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError
    from typing import Literal
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    print("⚠  pydantic not installed. Run: pip install pydantic")
    # Dummy classes so rest of file doesn't break
    class BaseModel: pass
    class Field:
        def __init__(self, *a, **kw): pass
    ValidationError = ValueError
    Literal = None


class WeatherInput(BaseModel):
    """Get current weather for a city."""
    city: str = Field(description="City name to get weather for, e.g. 'Mumbai', 'Delhi'")
    units: Literal["celsius", "fahrenheit"] = Field(
        default="celsius",
        description="Temperature unit — celsius or fahrenheit"
    )


class CalculatorInput(BaseModel):
    """Safely evaluate a mathematical expression."""
    expression: str = Field(
        description="Math expression to evaluate, e.g. '2 + 3 * 4', '(10 + 5) / 3'",
        min_length=1,
        max_length=200
    )

    @field_validator("expression")
    @classmethod
    def validate_safe_expression(cls, v: str) -> str:
        # Only allow digits, operators, parens, spaces, dots, modulo
        if not re.match(r'^[\d\s\+\-\*\/\.\(\)\%]+$', v):
            raise ValueError(
                f"Unsafe expression: '{v}'. Only numbers and basic operators allowed."
            )
        return v.strip()


class DatabaseQueryInput(BaseModel):
    """Query a mock database table with optional filtering."""
    table: Literal["users", "products", "orders"] = Field(
        description="Table name to query: users, products, or orders"
    )
    filter_by: Optional[str] = Field(
        default=None,
        description="Filter condition as 'field=value', e.g. 'status=active'"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Max rows to return (1-100)"
    )


class SendEmailInput(BaseModel):
    """Send an email to a recipient."""
    to: str = Field(description="Recipient email address")
    subject: str = Field(description="Email subject line", min_length=1, max_length=200)
    body: str = Field(description="Email body content", min_length=1)

    @field_validator("to")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', v):
            raise ValueError(f"Invalid email address: '{v}'")
        return v.lower().strip()


class SearchProductInput(BaseModel):
    """Search products in catalog by query, category, and price range."""
    query: str = Field(
        description="Search text, e.g. 'laptop', 'running shoes size 10'",
        min_length=1,
        max_length=200
    )
    category: Optional[Literal["electronics", "clothing", "books", "home", "food"]] = Field(
        default=None,
        description="Category filter"
    )
    min_price: Optional[float] = Field(default=None, ge=0, description="Minimum price in INR")
    max_price: Optional[float] = Field(default=None, ge=0, description="Maximum price in INR")
    limit: int = Field(default=10, ge=1, le=50, description="Number of results")

    @model_validator(mode="after")
    def validate_price_range(self) -> "SearchProductInput":
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError(
                    f"min_price ({self.min_price}) cannot exceed max_price ({self.max_price})"
                )
        return self


# ── Schema converters ──────────────────────────────────────────────────────


def pydantic_to_openai_tool(name: str, description: str, model: type) -> dict:
    """Convert Pydantic model to OpenAI function calling format."""
    schema = model.model_json_schema()
    # Remove Pydantic metadata that OpenAI doesn't need
    schema.pop("title", None)
    schema.pop("$defs", None)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": schema,
        },
    }


def pydantic_to_anthropic_tool(name: str, description: str, model: type) -> dict:
    """Convert Pydantic model to Anthropic tool format."""
    schema = model.model_json_schema()
    schema.pop("title", None)
    schema.pop("$defs", None)
    return {
        "name": name,
        "description": description,
        "input_schema": schema,
    }


def demo_tool_definitions():
    """Section 1: Tool definition schemas demo."""
    print("\n" + "=" * 60)
    print("SECTION 1 — Tool Definition + JSON Schema")
    print("=" * 60)

    if not PYDANTIC_AVAILABLE:
        print("Pydantic not available, skipping demo.")
        return

    tool_specs = [
        ("get_weather", "Get current weather for a city", WeatherInput),
        ("calculate", "Safely evaluate a math expression", CalculatorInput),
        ("query_database", "Query a database table with optional filter", DatabaseQueryInput),
        ("send_email", "Send an email to a recipient", SendEmailInput),
        ("search_products", "Search products by query and filters", SearchProductInput),
    ]

    print("\n── OpenAI Format Tools ─────────────────────────────────")
    openai_tools = []
    for name, desc, model in tool_specs:
        tool = pydantic_to_openai_tool(name, desc, model)
        openai_tools.append(tool)
        print(f"\n[Tool] {name}")
        # Show schema properties only (not full JSON to keep output readable)
        params = tool["function"]["parameters"]
        props = params.get("properties", {})
        required = params.get("required", [])
        for prop_name, prop_schema in props.items():
            req_marker = "*" if prop_name in required else " "
            ptype = prop_schema.get("type", prop_schema.get("enum", "?"))
            pdesc = prop_schema.get("description", "")[:60]
            print(f"  {req_marker} {prop_name:<20} {str(ptype):<15} {pdesc}")

    print("\n── Anthropic Format (first 2 tools) ────────────────────")
    for name, desc, model in tool_specs[:2]:
        tool = pydantic_to_anthropic_tool(name, desc, model)
        print(f"\n[Tool] {tool['name']}")
        print(f"  input_schema keys: {list(tool['input_schema'].get('properties', {}).keys())}")

    print("\n── Full JSON Schema Example (WeatherInput) ─────────────")
    print(json.dumps(WeatherInput.model_json_schema(), indent=2))

    return openai_tools


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 2 — Tool Executor with Validation + Audit Log
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class ToolResult:
    """Result object returned by ToolExecutor."""
    tool_name: str
    success: bool
    result: Any
    error: Optional[str] = None
    duration_ms: float = 0.0

    def to_llm_content(self) -> str:
        """Convert to string that LLM can understand."""
        if self.success:
            if isinstance(self.result, (dict, list)):
                return json.dumps(self.result, indent=2)
            return str(self.result)
        return json.dumps({
            "error": "tool_execution_failed",
            "message": self.error,
            "retry": True,
        })

    def __str__(self):
        status = "✓" if self.success else "✗"
        dur = f"{self.duration_ms:.1f}ms"
        if self.success:
            preview = str(self.result)[:80]
            return f"{status} {self.tool_name} [{dur}] → {preview}"
        return f"{status} {self.tool_name} [{dur}] ERROR: {self.error}"


class ToolExecutor:
    """
    Central tool registry + executor with:
    - Pydantic validation
    - Error handling + structured errors
    - Audit logging
    - Parallel async execution
    - Rate limiting
    """

    def __init__(self, rate_limit_per_minute: int = 60):
        self._tools: dict[str, dict] = {}
        self._call_log: list[dict] = []
        self._rate_limiter = RateLimiter(
            max_calls=rate_limit_per_minute, window_seconds=60
        )

    def register(
        self,
        name: str,
        fn: Callable,
        input_model: Optional[type] = None,
        description: str = "",
    ):
        """Register a tool function with optional Pydantic schema."""
        self._tools[name] = {
            "fn": fn,
            "schema": input_model,
            "description": description,
        }
        logger.debug(f"Tool registered: {name}")

    def execute(
        self, tool_name: str, tool_args: dict, user_id: str = "anonymous"
    ) -> ToolResult:
        """Execute a tool synchronously with full error handling."""
        # Rate limit check
        if not self._rate_limiter.check(user_id, tool_name):
            return ToolResult(
                tool_name=tool_name,
                success=False,
                result=None,
                error=f"Rate limit exceeded for tool '{tool_name}'",
                duration_ms=0,
            )

        # Tool existence check
        if tool_name not in self._tools:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                result=None,
                error=f"Unknown tool: '{tool_name}'. Available: {list(self._tools.keys())}",
            )

        tool = self._tools[tool_name]
        start = time.perf_counter()

        try:
            # Pydantic validation
            if tool["schema"] and PYDANTIC_AVAILABLE:
                validated = tool["schema"].model_validate(tool_args)
                args = validated.model_dump()
            else:
                args = tool_args

            result = tool["fn"](**args)
            duration = (time.perf_counter() - start) * 1000

            # Audit log (sanitize sensitive fields)
            self._log_call(user_id, tool_name, tool_args, True, duration)
            return ToolResult(tool_name, True, result, duration_ms=duration)

        except ValidationError as e:
            duration = (time.perf_counter() - start) * 1000
            error_msg = f"Validation failed: {e.errors()}"
            self._log_call(user_id, tool_name, tool_args, False, duration, error_msg)
            return ToolResult(tool_name, False, None, error_msg, duration)

        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            error_msg = str(e)
            logger.warning(f"Tool '{tool_name}' failed: {error_msg}")
            self._log_call(user_id, tool_name, tool_args, False, duration, error_msg)
            return ToolResult(tool_name, False, None, error_msg, duration)

    async def execute_async(
        self, tool_name: str, tool_args: dict, user_id: str = "anonymous"
    ) -> ToolResult:
        """Async wrapper — runs sync tool in thread pool."""
        return await asyncio.to_thread(self.execute, tool_name, tool_args, user_id)

    async def execute_parallel(
        self, calls: list[tuple[str, dict]], user_id: str = "anonymous"
    ) -> list[ToolResult]:
        """
        Execute multiple tools in parallel using asyncio.gather.
        calls = [(tool_name, args), ...]
        """
        tasks = [self.execute_async(name, args, user_id) for name, args in calls]
        return await asyncio.gather(*tasks)

    def print_audit_log(self):
        """Print formatted audit log of all tool calls."""
        print(f"\n{'─'*55}")
        print(f"{'TOOL':<22} {'STATUS':<8} {'DURATION':>10}  USER")
        print(f"{'─'*55}")
        for entry in self._call_log:
            status = "OK" if entry["success"] else "ERR"
            dur = f"{entry.get('duration_ms', 0):.1f}ms"
            print(f"  {entry['tool']:<20} {status:<8} {dur:>10}  {entry['user_id']}")
        print(f"{'─'*55}")
        total = len(self._call_log)
        ok = sum(1 for e in self._call_log if e["success"])
        print(f"  Total: {total} calls | OK: {ok} | Failed: {total - ok}")

    def _log_call(
        self,
        user_id: str,
        tool: str,
        args: dict,
        success: bool,
        duration: float,
        error: str = None,
    ):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "tool": tool,
            "args_keys": list(args.keys()),
            "success": success,
            "duration_ms": duration,
        }
        if error:
            entry["error"] = error
        self._call_log.append(entry)
        audit_logger.debug(f"AUDIT: {json.dumps(entry)}")


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 3 — Actual Tool Implementations (Mock Data)
# ══════════════════════════════════════════════════════════════════════════════

# Mock data store — consistent results across calls
_MOCK_USERS = [
    {"id": i, "name": f"User_{i:03d}", "email": f"user{i}@example.com",
     "status": "active" if i % 3 != 0 else "inactive",
     "city": random.choice(["Mumbai", "Delhi", "Bangalore", "Chennai"])}
    for i in range(1, 21)
]

_MOCK_PRODUCTS = [
    {"id": i, "name": f"Product_{i:03d}", "category": random.choice(
        ["electronics", "clothing", "books", "home"]),
     "price": round(random.uniform(100, 100000), 2),
     "stock": random.randint(0, 50),
     "rating": round(random.uniform(3.0, 5.0), 1)}
    for i in range(1, 21)
]

_MOCK_ORDERS = [
    {"id": i, "user_id": random.randint(1, 10),
     "product_id": random.randint(1, 20),
     "total": round(random.uniform(200, 50000), 2),
     "status": random.choice(["pending", "processing", "shipped", "completed", "cancelled"]),
     "created_at": f"2024-01-{i:02d}"}
    for i in range(1, 21)
]


def get_weather(city: str, units: str = "celsius") -> dict:
    """Mock weather API — returns realistic data for known cities."""
    WEATHER_DATA = {
        "mumbai":     {"temp_c": 32, "humidity": 85, "condition": "Humid & Hazy"},
        "delhi":      {"temp_c": 38, "humidity": 35, "condition": "Hot & Dusty"},
        "bangalore":  {"temp_c": 24, "humidity": 70, "condition": "Pleasant"},
        "chennai":    {"temp_c": 34, "humidity": 80, "condition": "Hot & Humid"},
        "kolkata":    {"temp_c": 30, "humidity": 75, "condition": "Warm"},
        "london":     {"temp_c": 14, "humidity": 82, "condition": "Cloudy"},
        "new york":   {"temp_c": 22, "humidity": 60, "condition": "Clear"},
        "tokyo":      {"temp_c": 18, "humidity": 65, "condition": "Partly Cloudy"},
        "dubai":      {"temp_c": 40, "humidity": 45, "condition": "Very Hot"},
        "singapore":  {"temp_c": 29, "humidity": 88, "condition": "Tropical"},
    }
    data = WEATHER_DATA.get(city.lower(), {"temp_c": 22, "humidity": 65, "condition": "Unknown"})
    temp = data["temp_c"]
    if units == "fahrenheit":
        temp = round(temp * 9 / 5 + 32, 1)
    return {
        "city": city.title(),
        "temperature": temp,
        "units": units,
        "humidity_percent": data["humidity"],
        "condition": data["condition"],
        "timestamp": datetime.utcnow().isoformat(),
    }


def calculate(expression: str) -> dict:
    """Safe calculator — validates expression before eval."""
    try:
        # Deliberately restricted eval — no builtins, no globals
        result = eval(expression, {"__builtins__": {}}, {})
        return {
            "expression": expression,
            "result": result,
            "result_type": type(result).__name__,
        }
    except ZeroDivisionError:
        raise ValueError("Division by zero is not allowed")
    except Exception as e:
        raise ValueError(f"Cannot evaluate expression: {e}")


def query_database(table: str, filter_by: Optional[str] = None, limit: int = 10) -> dict:
    """Mock database query with simple field=value filtering."""
    TABLE_MAP = {
        "users": _MOCK_USERS,
        "products": _MOCK_PRODUCTS,
        "orders": _MOCK_ORDERS,
    }
    rows = TABLE_MAP.get(table, []).copy()

    if filter_by and "=" in filter_by:
        field, value = filter_by.split("=", 1)
        field, value = field.strip(), value.strip()
        # Try numeric comparison too
        def matches(row):
            row_val = row.get(field)
            if row_val is None:
                return False
            # Try numeric
            try:
                return float(str(row_val)) == float(value)
            except (ValueError, TypeError):
                return str(row_val).lower() == value.lower()
        rows = [r for r in rows if matches(r)]

    return {
        "table": table,
        "filter": filter_by,
        "total_matching": len(rows),
        "returned": min(limit, len(rows)),
        "rows": rows[:limit],
    }


def send_email(to: str, subject: str, body: str) -> dict:
    """Mock email sender — prints confirmation, doesn't actually send."""
    # Simulate slight delay
    time.sleep(0.05)
    msg_id = f"MSG-{random.randint(10000, 99999)}"
    print(f"    📧 [EMAIL] To: {to} | Subject: '{subject}' | ID: {msg_id}")
    return {
        "sent": True,
        "message_id": msg_id,
        "to": to,
        "subject": subject,
        "timestamp": datetime.utcnow().isoformat(),
    }


def search_products(
    query: str,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: int = 10,
) -> dict:
    """Mock product search with text + category + price filtering."""
    results = _MOCK_PRODUCTS.copy()

    # Text filter
    q = query.lower()
    results = [p for p in results if q in p["name"].lower() or q in p["category"].lower()]

    # Category filter
    if category:
        results = [p for p in results if p["category"] == category]

    # Price filters
    if min_price is not None:
        results = [p for p in results if p["price"] >= min_price]
    if max_price is not None:
        results = [p for p in results if p["price"] <= max_price]

    # Sort by rating desc
    results.sort(key=lambda x: x["rating"], reverse=True)

    return {
        "query": query,
        "total_found": len(results),
        "returned": min(limit, len(results)),
        "products": results[:limit],
    }


def flaky_tool(fail_rate: float = 0.6) -> dict:
    """Tool that fails randomly — used to demo error recovery."""
    if random.random() < fail_rate:
        raise ConnectionError("External API timeout after 30s")
    return {"status": "success", "data": "some_value", "timestamp": datetime.utcnow().isoformat()}


# ── Build the global executor ──────────────────────────────────────────────

def build_executor() -> ToolExecutor:
    """Create and register all tools into a ToolExecutor."""
    executor = ToolExecutor(rate_limit_per_minute=100)

    executor.register("get_weather", get_weather, WeatherInput, "Get city weather")
    executor.register("calculate", calculate, CalculatorInput, "Math calculator")
    executor.register("query_database", query_database, DatabaseQueryInput, "DB query")
    executor.register("send_email", send_email, SendEmailInput, "Send email")
    executor.register(
        "search_products", search_products, SearchProductInput, "Search products"
    )
    executor.register("flaky_tool", flaky_tool, description="Unreliable external API")

    return executor


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 4 — Mock LLM + Agent Loop
# ══════════════════════════════════════════════════════════════════════════════

MAX_AGENT_ITERATIONS = 10


class MockLLM:
    """
    Simulates an LLM that decides which tools to call based on keyword matching.
    In real code: replace with openai.chat.completions.create() or anthropic.messages.create()
    """

    def decide_tools(self, user_message: str) -> list[tuple[str, dict]]:
        """Returns list of (tool_name, args) based on message content."""
        msg = user_message.lower()
        calls = []

        # Weather detection — can detect multiple cities
        city_keywords = {
            "mumbai": "Mumbai", "delhi": "Delhi", "bangalore": "Bangalore",
            "london": "London", "new york": "New York", "tokyo": "Tokyo",
            "singapore": "Singapore", "dubai": "Dubai",
        }
        detected_cities = [city_keywords[k] for k in city_keywords if k in msg]
        if detected_cities or "weather" in msg or "temperature" in msg:
            for city in detected_cities or ["Bangalore"]:
                units = "fahrenheit" if "fahrenheit" in msg else "celsius"
                calls.append(("get_weather", {"city": city, "units": units}))

        # Calculator detection
        if any(w in msg for w in ["calculate", "compute", "what is", "math", "evaluate"]):
            # Try to extract a math expression
            expr_match = re.search(r'[\d\s\+\-\*\/\(\)\.]+(?:[\+\-\*\/][\d\s\+\-\*\/\(\)\.]+)+', msg)
            if expr_match:
                calls.append(("calculate", {"expression": expr_match.group().strip()}))
            else:
                calls.append(("calculate", {"expression": "2 + 2"}))

        # Database detection
        if any(w in msg for w in ["show", "list", "get", "find", "database", "users", "products", "orders"]):
            if "product" in msg:
                calls.append(("query_database", {"table": "products", "limit": 5}))
            elif "order" in msg:
                calls.append(("query_database", {"table": "orders", "filter_by": "status=pending", "limit": 5}))
            else:
                calls.append(("query_database", {"table": "users", "filter_by": "status=active", "limit": 5}))

        # Email detection
        if "email" in msg or "send" in msg and "@" in msg:
            email_match = re.search(r'\b[\w.-]+@[\w.-]+\.\w+\b', msg)
            to_addr = email_match.group() if email_match else "user@example.com"
            calls.append(("send_email", {
                "to": to_addr,
                "subject": "Agent Notification",
                "body": f"Automated notification: {user_message[:100]}"
            }))

        return calls

    def synthesize_response(self, user_message: str, tool_results: list[ToolResult]) -> str:
        """Simulate LLM synthesizing a response from tool results."""
        if not tool_results:
            return (
                "I can help with weather, calculations, database queries, and emails. "
                "What would you like?"
            )

        parts = [f"Here is what I found:\n"]
        for tr in tool_results:
            if tr.success:
                if tr.tool_name == "get_weather":
                    d = tr.result
                    parts.append(
                        f"Weather in {d['city']}: {d['temperature']}°{d['units'][0].upper()}, "
                        f"Humidity {d['humidity_percent']}%, {d['condition']}"
                    )
                elif tr.tool_name == "calculate":
                    d = tr.result
                    parts.append(f"Calculation result: {d['expression']} = {d['result']}")
                elif tr.tool_name == "query_database":
                    d = tr.result
                    parts.append(
                        f"Found {d['total_matching']} records in '{d['table']}' "
                        f"(showing {d['returned']})"
                    )
                elif tr.tool_name == "send_email":
                    d = tr.result
                    parts.append(f"Email sent to {d['to']} (ID: {d['message_id']})")
                else:
                    parts.append(f"{tr.tool_name}: {str(tr.result)[:100]}")
            else:
                parts.append(f"⚠ {tr.tool_name} failed: {tr.error}")

        return "\n".join(parts)


class AgentLoop:
    """
    Agent loop that runs tool use cycle until completion or max iterations.
    Supports both mock and real LLM.
    """

    def __init__(self, executor: ToolExecutor, llm: MockLLM, max_iterations: int = MAX_AGENT_ITERATIONS):
        self.executor = executor
        self.llm = llm
        self.max_iterations = max_iterations

    def run(self, user_message: str, user_id: str = "demo_user") -> str:
        """Run the agent loop synchronously."""
        print(f"\n{'━'*60}")
        print(f"👤 User: {user_message}")
        print(f"{'━'*60}")

        iteration = 0
        accumulated_results: list[ToolResult] = []

        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n  [Iteration {iteration}/{self.max_iterations}]")

            # LLM decides tools
            tool_calls = self.llm.decide_tools(user_message)

            if not tool_calls:
                print("  → No tools needed, generating response...")
                break

            print(f"  → LLM requests {len(tool_calls)} tool call(s):")
            for name, args in tool_calls:
                print(f"     • {name}({args})")

            # Execute tools (parallel)
            results = asyncio.run(
                self.executor.execute_parallel(tool_calls, user_id)
            )

            print(f"\n  Tool Results:")
            for r in results:
                print(f"    {r}")

            accumulated_results.extend(results)

            # In real LLM: check if LLM wants more tools
            # In mock: we run once
            break

        response = self.llm.synthesize_response(user_message, accumulated_results)
        print(f"\n🤖 Agent Response:\n{response}")
        return response


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 5 — Parallel vs Sequential Tool Execution
# ══════════════════════════════════════════════════════════════════════════════

async def demo_parallel_tools(executor: ToolExecutor):
    """Benchmark parallel vs sequential tool execution."""
    print("\n" + "=" * 60)
    print("SECTION 5 — Parallel vs Sequential Execution")
    print("=" * 60)

    cities = ["Mumbai", "Delhi", "London", "Tokyo", "New York"]
    calls = [("get_weather", {"city": c, "units": "celsius"}) for c in cities]

    print(f"\n  Comparing {len(cities)} weather API calls:")

    # Sequential
    t0 = time.perf_counter()
    seq_results = []
    for name, args in calls:
        r = executor.execute(name, args, "seq_user")
        seq_results.append(r)
    t_seq = (time.perf_counter() - t0) * 1000

    # Parallel
    t0 = time.perf_counter()
    par_results = await executor.execute_parallel(calls, "par_user")
    t_par = (time.perf_counter() - t0) * 1000

    print(f"\n  {'Method':<15} {'Time':>10}  {'Speedup':>10}")
    print(f"  {'─'*40}")
    print(f"  {'Sequential':<15} {t_seq:>9.1f}ms  {'1.0x':>10}")
    speedup = t_seq / t_par if t_par > 0 else 1
    print(f"  {'Parallel':<15} {t_par:>9.1f}ms  {speedup:>9.1f}x")

    print(f"\n  Results comparison (both should match):")
    for i, (sr, pr) in enumerate(zip(seq_results, par_results)):
        match = "✓" if sr.result == pr.result else "✗"
        print(f"    {match} {cities[i]:<12}: {sr.result.get('temperature')}°C")

    print(f"\n  Note: With real I/O-bound calls (network, DB), parallel is")
    print(f"  dramatically faster. Here with mock data, overhead is minimal.")


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 6 — Tool Error Recovery Simulation
# ══════════════════════════════════════════════════════════════════════════════

async def demo_error_recovery(executor: ToolExecutor):
    """
    Simulate a scenario where:
    1. Tool fails with validation error → LLM corrects args
    2. Tool fails with transient error → retry logic kicks in
    3. Tool succeeds after correction
    """
    print("\n" + "=" * 60)
    print("SECTION 6 — Tool Error Recovery")
    print("=" * 60)

    print("\n── Scenario A: Validation Error Recovery ───────────────")
    print("  LLM sends wrong type for limit (string instead of int)")

    # Wrong args
    r1 = executor.execute("query_database", {
        "table": "users",
        "limit": "five"   # Wrong type!
    })
    print(f"\n  Attempt 1 (wrong args): {r1}")

    # LLM sees error, corrects
    print("  LLM reads error message, corrects 'five' → 5")
    r2 = executor.execute("query_database", {
        "table": "users",
        "limit": 5   # Correct
    })
    print(f"  Attempt 2 (corrected): {r2}")

    print("\n── Scenario B: Validation Error — min > max price ──────")
    r3 = executor.execute("search_products", {
        "query": "laptop",
        "min_price": 80000,
        "max_price": 30000   # min > max — invalid!
    })
    print(f"  Attempt (invalid range): {r3}")

    r4 = executor.execute("search_products", {
        "query": "laptop",
        "min_price": 30000,
        "max_price": 80000   # Fixed
    })
    print(f"  Attempt (fixed range): {r4}")

    print("\n── Scenario C: Transient Error Retry ───────────────────")
    print("  flaky_tool has 60% failure rate — retry until success")

    random.seed(42)   # Reproducible demo
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        r = executor.execute("flaky_tool", {"fail_rate": 0.6})
        print(f"  Attempt {attempt}: {'✓ Success' if r.success else f'✗ Failed — {r.error}'}")
        if r.success:
            print(f"  ✓ Recovered after {attempt} attempt(s)!")
            break
        if attempt < max_attempts:
            wait = 2 ** (attempt - 1) * 0.05   # Exponential backoff (scaled for demo)
            print(f"    Waiting {wait*1000:.0f}ms before retry (exponential backoff)")
            await asyncio.sleep(wait)
    else:
        print(f"  ✗ Failed after {max_attempts} attempts — giving up")

    print("\n── Scenario D: Unknown Tool ─────────────────────────────")
    r5 = executor.execute("nonexistent_tool", {"arg": "value"})
    print(f"  Unknown tool result: {r5}")


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 7 — Pydantic Validation Showcase
# ══════════════════════════════════════════════════════════════════════════════

def demo_pydantic_validation():
    """Showcase Pydantic validation for tool inputs."""
    print("\n" + "=" * 60)
    print("SECTION 7 — Pydantic Input Validation")
    print("=" * 60)

    if not PYDANTIC_AVAILABLE:
        print("Pydantic not available.")
        return

    test_cases = [
        # (description, model, input_data, should_pass)
        ("Valid weather input",
         WeatherInput, {"city": "Mumbai", "units": "celsius"}, True),

        ("Valid — units omitted (uses default)",
         WeatherInput, {"city": "Delhi"}, True),

        ("Invalid — city missing (required field)",
         WeatherInput, {"units": "celsius"}, False),

        ("Invalid — bad enum value",
         WeatherInput, {"city": "Mumbai", "units": "kelvin"}, False),

        ("Valid calculator expression",
         CalculatorInput, {"expression": "(100 + 50) * 2 / 5"}, True),

        ("Invalid — expression has letters (unsafe)",
         CalculatorInput, {"expression": "import os; os.system('ls')"}, False),

        ("Valid DB query",
         DatabaseQueryInput, {"table": "users", "filter_by": "status=active", "limit": 5}, True),

        ("Invalid — limit too high (>100)",
         DatabaseQueryInput, {"table": "orders", "limit": 500}, False),

        ("Invalid — wrong table name",
         DatabaseQueryInput, {"table": "admin_logs"}, False),

        ("Valid email",
         SendEmailInput, {"to": "test@example.com", "subject": "Hello", "body": "World"}, True),

        ("Invalid — bad email format",
         SendEmailInput, {"to": "not-an-email", "subject": "Test", "body": "Msg"}, False),

        ("Valid product search with price range",
         SearchProductInput, {"query": "laptop", "min_price": 20000, "max_price": 80000}, True),

        ("Invalid — min_price > max_price",
         SearchProductInput, {"query": "laptop", "min_price": 80000, "max_price": 20000}, False),
    ]

    print(f"\n  {'#':<3} {'Test Case':<45} {'Expected':<10} {'Actual':<10} {'Status'}")
    print(f"  {'─'*90}")

    for i, (desc, model, data, should_pass) in enumerate(test_cases, 1):
        try:
            validated = model.model_validate(data)
            passed = True
            detail = "validated OK"
        except (ValidationError, ValueError) as e:
            passed = False
            # Show first error only
            if hasattr(e, 'errors'):
                errs = e.errors()
                detail = errs[0].get('msg', str(e))[:50] if errs else str(e)[:50]
            else:
                detail = str(e)[:50]

        expected_str = "PASS" if should_pass else "FAIL"
        actual_str = "PASS" if passed else "FAIL"
        status = "✓" if passed == should_pass else "✗ MISMATCH"
        print(f"  {i:<3} {desc:<45} {expected_str:<10} {actual_str:<10} {status}")
        if passed != should_pass:
            print(f"      Detail: {detail}")

    # Show JSON schema generation
    print(f"\n── Auto-generated JSON Schema from Pydantic ────────────")
    print(f"  SearchProductInput.model_json_schema():")
    schema = SearchProductInput.model_json_schema()
    # Print just properties for brevity
    for prop, spec in schema.get("properties", {}).items():
        ptype = spec.get("type", spec.get("allOf", spec.get("anyOf", "?")))
        pdesc = spec.get("description", "")[:55]
        required_mark = "*" if prop in schema.get("required", []) else " "
        print(f"    {required_mark} {prop:<20} {str(ptype):<20} {pdesc}")
    print(f"\n  required fields: {schema.get('required', [])}")


# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 8 — Security Demos
# ══════════════════════════════════════════════════════════════════════════════

class RateLimiter:
    """Token bucket style rate limiter per user per tool."""

    def __init__(self, max_calls: int, window_seconds: int):
        self.max_calls = max_calls
        self.window = window_seconds
        self._calls: dict[str, list[float]] = defaultdict(list)

    def check(self, user_id: str, tool_name: str) -> bool:
        key = f"{user_id}:{tool_name}"
        now = time.monotonic()
        window_start = now - self.window

        # Purge old entries
        self._calls[key] = [t for t in self._calls[key] if t > window_start]

        if len(self._calls[key]) >= self.max_calls:
            return False

        self._calls[key].append(now)
        return True

    def remaining(self, user_id: str, tool_name: str) -> int:
        key = f"{user_id}:{tool_name}"
        now = time.monotonic()
        window_start = now - self.window
        recent = [t for t in self._calls[key] if t > window_start]
        return max(0, self.max_calls - len(recent))


def demo_security():
    """Showcase security features: path traversal, rate limiting, SQL injection prevention."""
    print("\n" + "=" * 60)
    print("SECTION 8 — Tool Security")
    print("=" * 60)

    # ── Path traversal prevention ──────────────────────────────────
    print("\n── A. Path Traversal Prevention ────────────────────────")
    ALLOWED_BASE = "/var/app/user_files"

    def safe_read_file(filename: str) -> str:
        safe_path = Path(ALLOWED_BASE) / filename
        try:
            resolved = safe_path.resolve()
            base_resolved = Path(ALLOWED_BASE).resolve()
            resolved.relative_to(base_resolved)  # Raises if outside
            return f"[Would read: {resolved}]"
        except ValueError:
            raise PermissionError(f"Path traversal detected! '{filename}' is outside allowed dir")

    test_paths = [
        ("report.txt", True),
        ("subdir/data.csv", True),
        ("../../etc/passwd", False),
        ("../secret.key", False),
        ("/absolute/path/evil.sh", False),
    ]
    for path, should_allow in test_paths:
        try:
            result = safe_read_file(path)
            status = "✓ ALLOWED" if should_allow else "✗ SHOULD DENY"
            print(f"  {status}: '{path}' → {result}")
        except PermissionError as e:
            status = "✓ BLOCKED" if not should_allow else "✗ SHOULD ALLOW"
            print(f"  {status}: '{path}' → {e}")

    # ── SQL injection prevention ────────────────────────────────────
    print("\n── B. SQL Injection Prevention ─────────────────────────")
    ATTACK_INPUTS = [
        "Robert",
        "Robert'; DROP TABLE users; --",
        "' OR '1'='1",
        "admin'--",
    ]
    for name in ATTACK_INPUTS:
        # Safe: parameterized
        safe_query = f"SELECT * FROM users WHERE name = %s (params: {repr(name)})"
        # Unsafe: f-string (NEVER do this!)
        unsafe_query = f"SELECT * FROM users WHERE name = '{name}'"
        print(f"  Input: {repr(name)[:40]}")
        print(f"    ✓ Safe (parameterized): {safe_query[:60]}")
        print(f"    ✗ Unsafe (f-string):    {unsafe_query[:60]}")

    # ── Rate limiting demo ──────────────────────────────────────────
    print("\n── C. Rate Limiting (3 calls per 10 seconds) ───────────")
    rl = RateLimiter(max_calls=3, window_seconds=10)

    for attempt in range(1, 6):
        allowed = rl.check("user_attacker", "expensive_tool")
        remaining = rl.remaining("user_attacker", "expensive_tool")
        status = "✓ ALLOWED" if allowed else "✗ BLOCKED (rate limit)"
        print(f"  Call #{attempt}: {status} | Remaining: {remaining}")

    # ── Audit logging demo ─────────────────────────────────────────
    print("\n── D. Audit Log Sample ─────────────────────────────────")
    sample_logs = [
        {"ts": "10:00:01", "user": "user_123", "tool": "query_database",
         "args_keys": ["table", "limit"], "success": True, "duration_ms": 12.3},
        {"ts": "10:00:02", "user": "user_456", "tool": "send_email",
         "args_keys": ["to", "subject", "body"], "success": True, "duration_ms": 45.1},
        {"ts": "10:00:03", "user": "user_789", "tool": "delete_records",
         "args_keys": ["table", "filter"], "success": False, "duration_ms": 2.1,
         "error": "Permission denied: insufficient role"},
    ]
    for log in sample_logs:
        status = "OK " if log["success"] else "ERR"
        error = f" | error: {log.get('error', '')}" if not log["success"] else ""
        print(f"  [{log['ts']}] {status} user={log['user']} tool={log['tool']}"
              f" args={log['args_keys']} {log['duration_ms']:.1f}ms{error}")


# ══════════════════════════════════════════════════════════════════════════════
#  REAL LLM DEMO (optional — only runs with API keys)
# ══════════════════════════════════════════════════════════════════════════════

async def demo_real_llm(executor: ToolExecutor):
    """
    Run actual tool use with OpenAI or Anthropic API.
    Only executes if USE_REAL_LLM is True.
    """
    if not USE_REAL_LLM:
        print("\n[Real LLM demo skipped — no API key set]")
        return

    if os.getenv("ANTHROPIC_API_KEY"):
        await _demo_anthropic(executor)
    elif os.getenv("OPENAI_API_KEY"):
        await _demo_openai(executor)


async def _demo_anthropic(executor: ToolExecutor):
    """Real Anthropic tool use demo."""
    try:
        import anthropic
    except ImportError:
        print("  pip install anthropic to use real Anthropic API")
        return

    client = anthropic.Anthropic()
    tools_list = [
        pydantic_to_anthropic_tool("get_weather", "Get weather for a city", WeatherInput),
        pydantic_to_anthropic_tool("calculate", "Evaluate math expression", CalculatorInput),
        pydantic_to_anthropic_tool("query_database", "Query database", DatabaseQueryInput),
    ]
    tool_fns = {
        "get_weather": get_weather,
        "calculate": calculate,
        "query_database": query_database,
    }

    messages = [{"role": "user", "content": "Mumbai aur Delhi ka weather celsius mein batao"}]

    print("\n[Real Anthropic API] Running tool use loop...")
    while True:
        resp = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            tools=tools_list,
            messages=messages,
        )
        print(f"  stop_reason: {resp.stop_reason}")

        if resp.stop_reason == "end_turn":
            for block in resp.content:
                if block.type == "text":
                    print(f"  Final: {block.text}")
            break

        if resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})
            tool_results = []
            for block in resp.content:
                if block.type == "tool_use":
                    print(f"  Calling: {block.name}({block.input})")
                    r = executor.execute(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": r.to_llm_content(),
                    })
            messages.append({"role": "user", "content": tool_results})
        else:
            break


async def _demo_openai(executor: ToolExecutor):
    """Real OpenAI function calling demo."""
    try:
        import openai
    except ImportError:
        print("  pip install openai to use real OpenAI API")
        return

    client = openai.AsyncOpenAI()
    tools_list = [
        pydantic_to_openai_tool("get_weather", "Get weather for a city", WeatherInput),
        pydantic_to_openai_tool("calculate", "Evaluate math expression", CalculatorInput),
    ]
    tool_fns = {"get_weather": get_weather, "calculate": calculate}

    messages = [{"role": "user", "content": "Mumbai ka weather batao aur 150 * 7 calculate karo"}]

    print("\n[Real OpenAI API] Running tool use loop...")
    while True:
        resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools_list,
            tool_choice="auto",
        )
        choice = resp.choices[0]
        print(f"  finish_reason: {choice.finish_reason}")

        if choice.finish_reason == "stop":
            print(f"  Final: {choice.message.content}")
            break

        if choice.finish_reason == "tool_calls":
            messages.append(choice.message)
            for tc in choice.message.tool_calls:
                args = json.loads(tc.function.arguments)
                print(f"  Calling: {tc.function.name}({args})")
                r = executor.execute(tc.function.name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": r.to_llm_content(),
                })
        else:
            break


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN — Section runners
# ══════════════════════════════════════════════════════════════════════════════

def run_section1():
    demo_tool_definitions()

def run_section2(executor):
    print("\n" + "=" * 60)
    print("SECTION 2 — Tool Executor Demo")
    print("=" * 60)

    print("\n── Single tool calls ───────────────────────────────────")
    r = executor.execute("get_weather", {"city": "Mumbai"})
    print(f"  {r}")

    r = executor.execute("calculate", {"expression": "100 * 3.14159"})
    print(f"  {r}")

    r = executor.execute("query_database", {"table": "orders", "filter_by": "status=completed", "limit": 3})
    print(f"  {r}")

    print("\n── Audit Log ───────────────────────────────────────────")
    executor.print_audit_log()

def run_section3(executor):
    asyncio.run(demo_parallel_tools(executor))

def run_section4(executor):
    print("\n" + "=" * 60)
    print("SECTION 4 — Agent Loop Demo")
    print("=" * 60)

    llm = MockLLM()
    agent = AgentLoop(executor, llm)

    test_messages = [
        "Mumbai aur Delhi ka weather celsius mein compare karo",
        "Show me 5 active users from database",
        "Calculate 150 * 7 + 200 / 4",
        "Show me pending orders",
        "What is the weather in Tokyo and Singapore?",
    ]

    for msg in test_messages:
        agent.run(msg)

def run_section5(executor):
    asyncio.run(demo_error_recovery(executor))

def run_section6():
    demo_pydantic_validation()

def run_section7():
    demo_security()


def main():
    args = sys.argv[1:] if len(sys.argv) > 1 else ["all"]
    arg = args[0].lower() if args else "all"

    print("\n" + "╔" + "═" * 58 + "╗")
    print("║  Advanced LLM Tool Use — Practical Demo" + " " * 18 + "║")
    print("║  40 LPA Interview Prep Series — File 02" + " " * 18 + "║")
    print("╚" + "═" * 58 + "╝")

    executor = build_executor()

    if arg in ("all", "demo"):
        run_section1()
        run_section2(executor)
        run_section3(executor)
        run_section4(executor)
        run_section5(executor)
        run_section6()
        run_section7()
        if USE_REAL_LLM:
            asyncio.run(demo_real_llm(executor))

    elif arg == "section1":
        run_section1()
    elif arg == "section2":
        run_section2(executor)
    elif arg == "section3":
        run_section3(executor)
    elif arg == "section4":
        run_section4(executor)
    elif arg == "section5":
        run_section5(executor)
    elif arg == "section6":
        run_section6()
    elif arg == "section7":
        run_section7()
    else:
        print(f"Unknown section: {arg}")
        print("Usage: python 02_tool_use_advanced.py [all|section1|section2|section3|section4|section5|section6|section7]")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("All demos complete!")
    print("  Set ANTHROPIC_API_KEY or OPENAI_API_KEY for real LLM demos.")
    print("=" * 60)


if __name__ == "__main__":
    main()
