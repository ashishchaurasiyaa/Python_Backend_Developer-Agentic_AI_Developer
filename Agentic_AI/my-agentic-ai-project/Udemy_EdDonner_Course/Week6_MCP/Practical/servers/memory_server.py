"""
MEMORY SERVER (FastMCP, stdio) — Week 6 MCP, Lab 3 ka pehla server (L112, L118-L121).

KYA HAI YE?
-----------
MCP SERVER 3 TYPES ke hote hain (L118 me Ed ne bataya):
  (a) LOCAL stdio server jo SAARA kaam khud karta hai (local files/compute)
      --> YE WALA server type (a) hai: memory ek local JSON file me store hoti hai.
  (b) LOCAL stdio server jo andar se REMOTE API call karta hai
      (course ke Brave Search aur Polygon servers yahi hain — server local
       chalta hai par data internet se laata hai, API key chahiye hoti hai).
  (c) FULLY REMOTE server (SSE/HTTP transport) — server kisi aur machine par.

COURSE me Ed "knowledge-graph memory server" (npx wala, Anthropic ka reference
server) use karta hai jo entities + observations store karta hai. Humara FREE
substitute wahi shape sikhata hai: entity (jaise 'watchlist') ke against facts
save/recall karna — bas storage JSON file hai, Node/npx ki zaroorat nahi.

PERSISTENCE KA POINT: stdio server har client connection par naya subprocess
hota hai — RAM me kuch nahi bachta. Isliye memory ko DISK (memory.json) par
likhna zaroori hai, tabhi agent ke alag-alag runs me yaadein survive karti hain.

RUN (standalone test ke liye — normally client isse subprocess me launch karta hai):
  cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
  uv run Udemy_EdDonner_Course/Week6_MCP/Practical/servers/memory_server.py
"""

import json
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# FastMCP = high-level decorator API. @mcp.tool() lagao, function ka
# signature + docstring se SDK khud JSON-schema bana ke client ko advertise
# karta hai (tools/list response me). Yahi "tool discovery" hai.
mcp = FastMCP("memory_server", log_level="ERROR")  # INFO logs stderr par shor karte hain

# Storage path __file__ se nikala — kyunki stdio subprocess ka cwd kuch bhi ho
# sakta hai (client jahan se launch kare), relative path risky hota.
MEMORY_FILE = Path(__file__).resolve().parent.parent / "output" / "memory.json"


def _load() -> dict:
    """memory.json ko dict me load karo. File nahi hai to empty store."""
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save(store: dict) -> None:
    """Store ko wapas disk par likho (pretty-printed, taaki insaan padh sake)."""
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE.write_text(json.dumps(store, indent=2))


@mcp.tool()
def save_memory(entity: str, fact: str) -> str:
    """Kisi entity (jaise 'watchlist' ya kisi insaan ka naam) ke baare me ek fact save karta hai. Baad me recall_memories se wapas mil jayega."""
    store = _load()
    store.setdefault(entity, []).append(
        {"fact": fact, "saved_at": datetime.now().isoformat(timespec="seconds")}
    )
    _save(store)
    return f"Saved fact for entity '{entity}'. Ab is entity ke paas {len(store[entity])} fact(s) hain."


# NOTE: list ki jagah dict return kar rahe hain — empty list MCP me EMPTY
# content ban jaati hai, aur Chat Completions empty tool-output par warning
# deke placeholder daal deta hai. Dict hamesha ek non-empty JSON text deta hai.
@mcp.tool()
def recall_memories(entity: str) -> dict:
    """Entity ke saare saved facts wapas deta hai. 'facts' list empty ho to is entity ki koi yaad nahi."""
    store = _load()
    facts = [item["fact"] for item in store.get(entity, [])]
    return {"entity": entity, "count": len(facts), "facts": facts}


@mcp.tool()
def list_entities() -> dict:
    """Memory me jitni bhi entities save hain unke naam batata hai."""
    names = sorted(_load().keys())
    return {"count": len(names), "entities": names}


if __name__ == "__main__":
    # stdio transport: server stdin se JSON-RPC padhta hai, stdout par jawab
    # likhta hai. ISLIYE server code me print() mat karo — wo protocol stream
    # corrupt kar dega! Logging chahiye to stderr use karo.
    mcp.run(transport="stdio")
