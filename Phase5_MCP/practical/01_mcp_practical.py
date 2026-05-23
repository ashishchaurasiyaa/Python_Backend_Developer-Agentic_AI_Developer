"""
Phase5_MCP — Complete Practical
==================================
Topics:
  1. MCP (Model Context Protocol) concepts
  2. MCP Server: exposing tools, resources, prompts
  3. MCP Client: connecting to server
  4. Tool definitions (matching OpenAI/Claude format)
  5. Resources (files, databases, APIs)
  6. Prompts (reusable prompt templates)
  7. Real-world patterns: database MCP, filesystem MCP

Install: pip install mcp anthropic
Run: python 01_mcp_practical.py
"""

import os, json, asyncio
from typing import Any, Dict, List, Optional

print("=" * 60)
print("MCP (Model Context Protocol) CONCEPTS")
print("=" * 60)

MCP_CONCEPTS = {
    "MCP":          "Open protocol for LLMs to interact with tools/data (like USB-C for AI)",
    "MCP Server":   "Exposes tools/resources/prompts via MCP protocol (you build these)",
    "MCP Client":   "Connects to MCP server, used by LLM host (Claude Desktop, Claude Code)",
    "Tool":         "Function the LLM can call (like function calling)",
    "Resource":     "Data source the LLM can read (files, DB rows, API responses)",
    "Prompt":       "Reusable prompt template with arguments",
    "Transport":    "How client/server communicate: stdio (local) or HTTP+SSE (remote)",
    "Host":         "The LLM application (Claude Desktop, IDEs) that uses MCP clients",
}
for k, v in MCP_CONCEPTS.items():
    print(f"  {k:<16}: {v}")

print("\n  MCP Architecture:")
print("  Host (Claude Desktop)")
print("    └── MCP Client 1 ──── MCP Server A (filesystem tools)")
print("    └── MCP Client 2 ──── MCP Server B (database tools)")
print("    └── MCP Client 3 ──── MCP Server C (web search)")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: MCP Server
# INTERVIEW: Server exposes tools/resources/prompts via MCP
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 1: Building an MCP Server")
print("=" * 60)

MCP_SERVER_CODE = '''\
from mcp.server.fastmcp import FastMCP
from mcp import types
import json, os

# ── Create MCP server ──────────────────────────────────────────
mcp = FastMCP("my-tools-server")

# ── Tool (function the LLM can call) ──────────────────────────
# INTERVIEW: @mcp.tool() = expose function as MCP tool
@mcp.tool()
async def get_weather(city: str, units: str = "celsius") -> str:
    """
    Get the current weather for a city.
    Args:
        city:  City name (e.g., "London")
        units: Temperature units: celsius or fahrenheit
    """
    # Real implementation: call weather API
    temp  = 18 if units == "celsius" else 64
    return json.dumps({
        "city":        city,
        "temperature": f"{temp}°{'C' if units == 'celsius' else 'F'}",
        "condition":   "Partly cloudy",
        "humidity":    "65%",
    })

@mcp.tool()
async def run_sql_query(query: str, database: str = "main") -> str:
    """
    Execute a read-only SQL query on the database.
    ONLY SELECT statements are allowed.
    Args:
        query:    SQL SELECT statement
        database: Database name (main, analytics, archive)
    """
    if not query.strip().upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed")
    # Real: execute against actual DB
    return json.dumps({"rows": [{"id": 1, "name": "Example"}], "count": 1})

@mcp.tool()
async def create_file(path: str, content: str) -> str:
    """Create a file with the given content."""
    safe_path = os.path.join("/tmp/mcp_files", os.path.basename(path))
    os.makedirs(os.path.dirname(safe_path), exist_ok=True)
    with open(safe_path, "w") as f:
        f.write(content)
    return f"File created: {safe_path}"

# ── Resource (data the LLM can read) ──────────────────────────
# INTERVIEW: Resources = context the LLM reads, not calls
@mcp.resource("config://app-settings")
async def get_app_settings() -> str:
    """Returns current application settings as JSON."""
    return json.dumps({
        "environment": os.getenv("ENV", "development"),
        "debug":       True,
        "version":     "1.2.3",
        "features":    ["rag", "streaming", "tools"],
    })

@mcp.resource("db://users/{user_id}")
async def get_user(user_id: str) -> str:
    """Get user data from database by ID."""
    # Real: fetch from DB
    return json.dumps({"id": user_id, "name": "Alice", "role": "admin"})

# ── Prompt template ───────────────────────────────────────────
@mcp.prompt()
async def code_review_prompt(code: str, language: str = "python") -> list:
    """Reusable code review prompt template."""
    return [
        {
            "role": "user",
            "content": f"Review this {language} code for bugs and style issues:\\n\\n```{language}\\n{code}\\n```\\n\\nProvide: bugs found, suggestions, score 1-10."
        }
    ]

# ── Run server ─────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")   # local: via stdio
    # mcp.run(transport="sse", host="0.0.0.0", port=8080)  # remote: HTTP+SSE
'''
print(MCP_SERVER_CODE[:900])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Low-level MCP Server
# INTERVIEW: More control over tool registration
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: Low-level MCP Server")
print("=" * 60)

LOW_LEVEL_CODE = '''\
from mcp.server import Server
from mcp import types
import mcp.server.stdio

server = Server("database-server")

# ── Register tool list ─────────────────────────────────────────
@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name        = "query_database",
            description = "Execute read-only SQL queries",
            inputSchema = {
                "type": "object",
                "properties": {
                    "query": {
                        "type":        "string",
                        "description": "SQL SELECT statement"
                    },
                    "limit": {
                        "type":        "integer",
                        "description": "Max rows to return",
                        "default":     100
                    },
                },
                "required": ["query"],
            }
        ),
    ]

# ── Handle tool calls ──────────────────────────────────────────
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "query_database":
        query = arguments["query"]
        limit = arguments.get("limit", 100)
        if not query.upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries allowed")
        # Execute query...
        result = {"rows": [], "affected": 0}
        return [types.TextContent(type="text", text=json.dumps(result))]
    raise ValueError(f"Unknown tool: {name}")

# ── Register resources ─────────────────────────────────────────
@server.list_resources()
async def list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri         = "schema://tables",
            name        = "Database Schema",
            description = "Current database table schema",
            mimeType    = "application/json",
        )
    ]

@server.read_resource()
async def read_resource(uri: str) -> str:
    if str(uri) == "schema://tables":
        return json.dumps({"tables": ["users", "orders", "products"]})
    raise ValueError(f"Unknown resource: {uri}")

# Run
async def main():
    async with mcp.server.stdio.stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

asyncio.run(main())
'''
print(LOW_LEVEL_CODE[:700])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: MCP Client
# INTERVIEW: Client connects to MCP server, used by LLM host
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: MCP Client")
print("=" * 60)

MCP_CLIENT_CODE = '''\
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import anthropic, json

async def use_mcp_tools():
    """
    INTERVIEW: MCP client connects to server, lists tools,
    then passes tools to LLM for function calling.
    """
    # ── Connect to MCP server ──────────────────────────────────
    server_params = StdioServerParameters(
        command = "python",
        args    = ["mcp_server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize connection
            await session.initialize()

            # ── List available tools ───────────────────────────
            tools_result = await session.list_tools()
            tools = tools_result.tools
            print([t.name for t in tools])
            # → ["get_weather", "run_sql_query", "create_file"]

            # ── Convert MCP tools to Claude format ────────────
            claude_tools = [
                {
                    "name":         t.name,
                    "description":  t.description,
                    "input_schema": t.inputSchema,
                }
                for t in tools
            ]

            # ── Use with Claude ────────────────────────────────
            client   = anthropic.Anthropic()
            messages = [{"role": "user", "content": "What\'s the weather in London?"}]

            # Agentic loop
            while True:
                response = client.messages.create(
                    model    = "claude-sonnet-4-5",
                    max_tokens = 1024,
                    tools    = claude_tools,
                    messages = messages,
                )

                if response.stop_reason == "end_turn":
                    print(response.content[0].text)
                    break

                # Handle tool use
                for block in response.content:
                    if block.type == "tool_use":
                        # Call the MCP tool
                        result = await session.call_tool(
                            block.name,
                            arguments=block.input,
                        )
                        # Add to message history
                        messages.extend([
                            {"role": "assistant", "content": response.content},
                            {"role": "user", "content": [{
                                "type":       "tool_result",
                                "tool_use_id": block.id,
                                "content":    result.content[0].text,
                            }]},
                        ])

asyncio.run(use_mcp_tools())
'''
print(MCP_CLIENT_CODE[:700])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: MCP Tool Schema
# INTERVIEW: JSON Schema defines tool inputs
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Tool Schema Design")
print("=" * 60)

# Show complete tool schema examples
TOOL_SCHEMAS = [
    {
        "name": "search_codebase",
        "description": "Search the codebase for code patterns or function definitions. Use when you need to find specific code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (regex or literal string)"
                },
                "file_extension": {
                    "type": "string",
                    "description": "Filter by file extension (e.g., 'py', 'ts')",
                    "enum": ["py", "ts", "js", "yaml", "json"]
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 100,
                }
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "execute_python",
        "description": "Execute Python code in a sandboxed environment. Returns stdout, stderr, and return value.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 10},
            },
            "required": ["code"]
        }
    }
]

print("\n  Example tool schemas:")
for schema in TOOL_SCHEMAS:
    print(f"\n  Tool: {schema['name']}")
    print(f"  Description: {schema['description'][:70]}...")
    props = list(schema["inputSchema"]["properties"].keys())
    required = schema["inputSchema"].get("required", [])
    print(f"  Properties: {props} (required: {required})")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: MCP vs Function Calling
# INTERVIEW: Know the distinction
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: MCP vs Function Calling vs LangChain Tools")
print("=" * 60)

COMPARISON = {
    "Feature":              ["MCP", "Function Calling", "LangChain Tools"],
    "Protocol":             ["Standard (MCP)", "Vendor-specific", "LangChain-specific"],
    "Server":               ["Separate process", "In-process", "In-process"],
    "Discovery":            ["list_tools() call", "Static definition", "Static list"],
    "Transport":            ["stdio/HTTP+SSE", "JSON in API", "Python calls"],
    "Persistence":          ["Server stays running", "Per-request", "Per-request"],
    "Use case":             ["IDE/Desktop plugins", "One-off API calls", "Agent pipelines"],
    "Reusability":          ["Server reusable by any host", "Per LLM vendor", "Per framework"],
}

print(f"\n  {'Feature':<20} {'MCP':<25} {'Function Calling':<25} {'LangChain'}")
print("  " + "-" * 90)
for feature, values in COMPARISON.items():
    if feature != "Feature":
        print(f"  {feature:<20} {values[0]:<25} {values[1]:<25} {values[2]}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Claude Desktop Config
# INTERVIEW: How to connect MCP server to Claude Desktop
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 6: Claude Desktop / Claude Code Integration")
print("=" * 60)

CLAUDE_CONFIG = '''\
// ~/Library/Application Support/Claude/claude_desktop_config.json
// INTERVIEW: This file registers MCP servers with Claude Desktop
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args":    ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/Documents"]
    },
    "my-python-server": {
      "command": "python",
      "args":    ["/path/to/my_mcp_server.py"],
      "env": {
        "DATABASE_URL": "postgresql://...",
        "API_KEY":      "sk-..."
      }
    },
    "postgres": {
      "command": "npx",
      "args":    ["-y", "@modelcontextprotocol/server-postgres"],
      "env":     {"POSTGRES_CONNECTION_STRING": "postgresql://localhost/mydb"}
    }
  }
}

// Claude Code (.mcp.json in project root)
{
  "mcpServers": {
    "project-tools": {
      "command": "python",
      "args":    ["tools/mcp_server.py"]
    }
  }
}
'''
print(CLAUDE_CONFIG)


# Demo: Mock MCP server implementation
class MockMCPServer:
    """Simplified mock of an MCP server for demonstration."""

    def __init__(self, name: str):
        self.name   = name
        self._tools = {}
        self._resources = {}

    def tool(self, func):
        """Register a tool (mock @mcp.tool() decorator)."""
        self._tools[func.__name__] = func
        return func

    def resource(self, uri: str):
        """Register a resource (mock @mcp.resource() decorator)."""
        def decorator(func):
            self._resources[uri] = func
            return func
        return decorator

    def list_tools(self) -> List[Dict]:
        return [
            {"name": name, "description": func.__doc__ or ""}
            for name, func in self._tools.items()
        ]

    async def call_tool(self, name: str, args: dict) -> str:
        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")
        func   = self._tools[name]
        result = func(**args)
        # handle async
        if asyncio.iscoroutine(result):
            result = await result
        return json.dumps(result) if not isinstance(result, str) else result


# Build and test mock server
server = MockMCPServer("demo-server")

@server.tool
def get_weather(city: str) -> dict:
    """Get weather for a city."""
    return {"city": city, "temp": "22°C", "condition": "sunny"}

@server.tool
def calculate(expression: str) -> dict:
    """Evaluate a math expression safely."""
    try:
        result = eval(expression, {"__builtins__": {}})
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}

@server.resource("config://settings")
def get_settings() -> dict:
    """Application settings."""
    return {"env": "dev", "debug": True}


print("\n  Mock MCP server demo:")
print(f"  Server: {server.name}")
print(f"  Tools: {[t['name'] for t in server.list_tools()]}")

result = asyncio.run(server.call_tool("get_weather", {"city": "London"}))
print(f"  call_tool('get_weather', city='London'): {result}")

result = asyncio.run(server.call_tool("calculate", {"expression": "2**10"}))
print(f"  call_tool('calculate', expression='2**10'): {result}")


print("\n" + "=" * 60)
print("MCP INTERVIEW SUMMARY:")
print("  MCP = standard protocol for LLMs to use tools (like USB-C for AI)")
print("  Server: exposes tools, resources, prompts via stdio or HTTP+SSE")
print("  Tools: functions LLM can call. Resources: data LLM can read.")
print("  FastMCP: @mcp.tool(), @mcp.resource(), @mcp.prompt() decorators")
print("  Client: list_tools() → pass to LLM → call_tool() on response")
print("  vs Function Calling: MCP is cross-vendor, reusable, separate process")
print("  Claude Desktop: register in claude_desktop_config.json")
print("=" * 60)
