"""
Modern Topics — Doc 8: MCP Advanced Server Dev (PRACTICAL)
=============================================================
Tries the real `mcp` SDK first; falls back to a manual server implementing
the same 4 handlers (list_tools, call_tool, list_resources, read_resource)
if it's not installed — same shape, no stdio transport, so it runs anywhere.

Topics covered:
  1. Tool schema definition — the exact JSON schema an MCP client sees
  2. Tool dispatch with a real security check (SELECT-only SQL guard)
  3. Resources — a second MCP primitive, distinct from tools
  4. A minimal MCP client simulating what Claude/an agent actually does:
     discover tools -> call one -> read a resource

Install (optional, real SDK): pip install "mcp[cli]"
Run: python 08_mcp_advanced_server_dev_practical.py
"""

try:
    import mcp  # noqa: F401
    HAS_MCP = True
except ImportError:
    HAS_MCP = False


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Tool Schema Definition
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Tool Schemas")
print("=" * 70)

if not HAS_MCP:
    print("\n  [mcp package not installed — demonstrating the CONCEPT with a manual")
    print("   server. `pip install \"mcp[cli]\"` for the real stdio-transport SDK.]")

TOOLS = [
    {
        "name": "query_database",
        "description": "Query the company database. SQL SELECT statements only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SQL SELECT query"},
                "database": {"type": "string", "enum": ["users_db", "orders_db"], "description": "Database name"},
            },
            "required": ["sql", "database"],
        },
    },
    {
        "name": "get_employee_info",
        "description": "Fetch employee information by employee ID.",
        "inputSchema": {
            "type": "object",
            "properties": {"employee_id": {"type": "string"}},
            "required": ["employee_id"],
        },
    },
]


def list_tools() -> list[dict]:
    """Mirrors @server.list_tools() — tells any MCP client what's callable."""
    return TOOLS


for tool in list_tools():
    print(f"\n  {tool['name']}: {tool['description']}")
    print(f"    required args: {tool['inputSchema']['required']}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Tool Dispatch, With a Real Security Check
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: call_tool() — Dispatch + Guard")
print("=" * 70)

FAKE_DB = {
    "users_db": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
    "orders_db": [{"order_id": 100, "user_id": 1, "total": 4500}],
}
FAKE_EMPLOYEES = {"E001": {"name": "Priya", "dept": "Engineering"}}


def call_tool(name: str, arguments: dict) -> str:
    """Mirrors @server.call_tool() — same dispatch shape as the doc, same
    SELECT-only guard the doc calls out as the security-relevant line."""
    if name == "query_database":
        sql = arguments["sql"]
        database = arguments["database"]

        if not sql.strip().upper().startswith("SELECT"):
            raise ValueError("Only SELECT queries allowed")  # the doc's exact guard

        # Toy "execution" — real code would run this against a real DB
        return str(FAKE_DB.get(database, []))

    if name == "get_employee_info":
        employee_id = arguments["employee_id"]
        return str(FAKE_EMPLOYEES.get(employee_id, "not found"))

    raise ValueError(f"Unknown tool: {name}")


print(f"\n  call_tool('query_database', {{'sql': 'SELECT * FROM users', 'database': 'users_db'}})")
print(f"    -> {call_tool('query_database', {'sql': 'SELECT * FROM users', 'database': 'users_db'})}")

print(f"\n  call_tool('query_database', {{'sql': 'DROP TABLE users', 'database': 'users_db'}})")
try:
    call_tool("query_database", {"sql": "DROP TABLE users", "database": "users_db"})
except ValueError as e:
    print(f"    -> BLOCKED: {e}")

print(f"\n  call_tool('get_employee_info', {{'employee_id': 'E001'}})")
print(f"    -> {call_tool('get_employee_info', {'employee_id': 'E001'})}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Resources — a Second MCP Primitive
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Resources (distinct from Tools)")
print("=" * 70)

print("""
  Tools = actions the model can INVOKE (with side effects or computation).
  Resources = content the model can READ, addressed by URI — closer to a
  file/document than a function call. An MCP server can expose both.
""")

RESOURCES = [{"uri": "company://docs/api-guide", "name": "API Documentation", "mimeType": "text/markdown"}]
RESOURCE_CONTENT = {"company://docs/api-guide": "# API Guide\n\nAll endpoints require a bearer token."}


def list_resources() -> list[dict]:
    return RESOURCES


def read_resource(uri: str) -> str:
    if uri in RESOURCE_CONTENT:
        return RESOURCE_CONTENT[uri]
    raise ValueError(f"Unknown resource: {uri}")


for r in list_resources():
    print(f"  Resource: {r['name']} ({r['uri']})")
print(f"\n  read_resource('company://docs/api-guide'):\n  {read_resource('company://docs/api-guide')!r}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: A Minimal MCP Client — What an Agent Actually Does
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 4: Client-Side — Discover, Then Call")
print("=" * 70)


def mcp_client_session(task: str):
    """Simulates what Claude (or any MCP-aware agent) does: discover
    available tools/resources FIRST, then decide which to invoke — this is
    why tool descriptions matter so much (Level7's semantic_kernel practical
    makes the same point from the framework side)."""
    print(f"  TASK: {task}")
    tools = list_tools()
    print(f"  1. Discovered {len(tools)} tools: {[t['name'] for t in tools]}")

    # A real client picks the right tool via an LLM call reading descriptions;
    # here, a simple keyword match stands in so this runs without a key.
    if "employee" in task.lower():
        chosen = "get_employee_info"
        args = {"employee_id": "E001"}
    else:
        chosen = "query_database"
        args = {"sql": "SELECT * FROM users", "database": "users_db"}

    print(f"  2. Chose tool: {chosen}({args})")
    result = call_tool(chosen, args)
    print(f"  3. Result: {result}")


mcp_client_session("Look up employee E001's department")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Add a 3rd tool `list_orders(user_id)` to TOOLS + call_tool(), backed by
   FAKE_DB['orders_db'].

MEDIUM:
2. If you have `mcp[cli]` installed: rewrite Sections 1-2 using the real
   `Server`, `@server.list_tools()`, `@server.call_tool()` decorators and
   `types.Tool`/`types.TextContent` — run it over real stdio transport.

HARD:
3. Add authorization to get_employee_info() — only allow it if a
   `requesting_user_role` argument is "hr" or "manager", raising
   PermissionError otherwise. This is the "Authorization check (neeche
   dekho)" comment the source doc leaves as a placeholder.

PRO:
4. Add a resource template (URI pattern like `company://employees/{id}`)
   instead of a fixed URI list — read_resource() should parse the ID out
   of the URI and look it up dynamically, the way a real MCP server exposing
   many similar resources would.
""")

if __name__ == "__main__":
    print("\nDone. Next: 09_ai_security_threats_practical.py")
