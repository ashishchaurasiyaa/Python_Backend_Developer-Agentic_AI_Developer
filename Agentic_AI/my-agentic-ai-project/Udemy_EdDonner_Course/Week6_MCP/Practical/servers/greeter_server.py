"""
GREETER SERVER — Hamara pehla MCP SERVER (FastMCP, stdio transport)
====================================================================

Ye file ek standalone MCP SERVER hai. Isme koi LLM nahi hai — pure Python
functions hain jo MCP protocol ke through TOOLS aur RESOURCES ke roop me
expose hote hain. Koi bhi MCP HOST (Claude Desktop, Cursor, hamara
Agents-SDK script) ise subprocess ke roop me spawn karke use kar sakta hai.

SERVER KA LIFECYCLE (stdio transport):
  1. Host/client ye command chalata hai:  uv run servers/greeter_server.py
  2. Ye process foreground me LOOP me baitha rehta hai — stdin se JSON-RPC
     messages padhta hai, stdout pe JSON-RPC responses likhta hai.
  3. Isliye is file ko seedha chalaoge to "kuch hota hua" nahi dikhega —
     wo client ke messages ka WAIT kar raha hota hai. Ise hamesha kisi
     MCP client ke through use karo (lab1_mcp_intro.py dekho).

FastMCP kya karta hai:
  - Low-level MCP spec (initialize handshake, tools/list, tools/call,
    resources/read JSON-RPC methods) ka saara boilerplate handle karta hai.
  - @mcp.tool() decorator: function ka NAME, DOCSTRING aur TYPE HINTS
    padhkar automatically JSON SCHEMA banata hai — yahi schema client ko
    "tools/list" response me jaata hai. Docstring achha likhna zaroori hai
    kyunki LLM isi description ko padhkar decide karta hai kaunsa tool
    kab call karna hai!
  - @mcp.resource("uri") decorator: RESOURCE expose karta hai. Tool vs
    Resource ka farak — TOOL ko LLM khud call karta hai (model-controlled),
    RESOURCE ko application/host padhta hai context dene ke liye
    (application-controlled). Jaise GET endpoint vs POST endpoint ka vibe.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

# Server ko ek naam do — client ko initialize handshake me yahi naam dikhega.
# log_level="WARNING": FastMCP by-default har request ka INFO log STDERR par
# chhapta hai (stdout nahi — wo protocol ke liye reserved hai). Host usi
# terminal me chal raha hai to ye logs lab ke output me mix ho jaate hain,
# isliye quiet kar diya. (Debugging me INFO kar lena — har tools/call dikhega.)
mcp = FastMCP("greeter_server", log_level="WARNING")


# ---------------------------------------------------------------------------
# TOOL #1 — zero-argument tool. Type hint `-> str` se FastMCP output type
# samajh leta hai; empty inputSchema generate hota hai.
# ---------------------------------------------------------------------------
@mcp.tool()
def get_server_time() -> str:
    """Server ka current date-time batata hai (Asia/Kolkata timezone me)."""
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    return now.strftime("%A, %d %B %Y %I:%M:%S %p IST")


# ---------------------------------------------------------------------------
# TOOL #2 — arguments wala tool. `name: str, style: str` type hints se
# FastMCP JSON schema banata hai: {"name": {"type": "string"}, ...}.
# LLM in param names + docstring ko padhkar sahi arguments bharta hai.
# ---------------------------------------------------------------------------
@mcp.tool()
def greet_in_style(name: str, style: str) -> str:
    """Diye gaye naam ko ek khaas style me greet karta hai.

    style options: 'pirate', 'shakespeare', 'hinglish', 'formal'.
    Agar style match na ho to ek simple default greeting milti hai.
    """
    styles = {
        "pirate": f"Arrr, ahoy there {name}! Welcome aboard, matey!",
        "shakespeare": f"Hark! Good morrow to thee, noble {name}!",
        "hinglish": f"Arre {name} bhai, kaise ho? Welcome welcome, badhiya laga aap aaye!",
        "formal": f"Good day, {name}. It is a pleasure to make your acquaintance.",
    }
    return styles.get(style.lower(), f"Hello, {name}! (style '{style}' nahi mila, default greeting)")


# ---------------------------------------------------------------------------
# RESOURCE — note: ye TOOL nahi hai. Resource = read-only data jo host
# apni marzi se context me daal sakta hai (LLM ise khud "call" nahi karta).
# URI scheme custom ho sakti hai — yahan "greeting://welcome".
# Client side pe: session.read_resource("greeting://welcome") se padhte hain.
# ---------------------------------------------------------------------------
@mcp.resource("greeting://welcome")
def welcome_message() -> str:
    """Server ka static welcome message (resource demo)."""
    return (
        "Welcome to greeter_server! Ye ek demo FastMCP server hai — "
        "2 tools (get_server_time, greet_in_style) aur ye 1 resource expose karta hai."
    )


if __name__ == "__main__":
    # transport="stdio" → server stdin/stdout par JSON-RPC bolega.
    # IMPORTANT: stdio server me kabhi print() mat karna (stdout protocol ke
    # liye reserved hai) — logging chahiye to stderr use karo.
    mcp.run(transport="stdio")
