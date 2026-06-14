"""
LAB 3 — MULTIPLE MCP SERVERS, EK AGENT: Memory + Market Data (L112, L118-L121)
==============================================================================

KYA SEEKHENGE
-------------
1. Ek agent ko EK SAATH KAI MCP servers dena: mcp_servers=[memory, market].
   Agents SDK dono servers ke tools merge karke LLM ko ek hi tool-list deta
   hai — agent ko pata bhi nahi chalta kaun sa tool kis server/process se aaya.
2. MCP SERVER KE 3 TYPES (L118):
   (a) local stdio, kaam khud kare        --> humara memory_server (JSON file)
   (b) local stdio, REMOTE API call kare  --> course ke Brave Search / Polygon
       servers yahi hain (API key chahiye)
   (c) fully remote (SSE/HTTP transport)  --> server doosri machine par
   Course Brave + Polygon use karta hai; humare FREE substitutes:
   memory = JSON-backed entity store (course ke knowledge-graph memory server
   jaisa), market = simulated deterministic prices (Polygon EOD jaisa shape).
3. PERSISTENCE across runs: memory server facts ko DISK par likhta hai,
   isliye Runner.run ka DOOSRA call (alag conversation!) bhi pehle call me
   save hua fact recall kar paata hai. Agent ki "yaaddasht" = MCP tool + file.

ARCHITECTURE (host/client/server yaad karo):
  HOST = ye Python script (+ Agents SDK)
  CLIENT = har MCPServerStdio apna alag MCP client session kholta hai
  SERVER = 2 alag subprocess: uv run memory_server.py, uv run market_server.py

KAISE CHALANA
-------------
  cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
  uv run Udemy_EdDonner_Course/Week6_MCP/Practical/lab3_memory_market_servers.py

LECTURES: L112 (multiple servers), L118 (server types), L119-L121 (Polygon/market servers)
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from agents import Agent, Runner, OpenAIChatCompletionsModel, set_tracing_disabled
from agents.mcp import MCPServerStdio

load_dotenv(override=True)
# OPENAI_API_KEY invalid hai — tracing OpenAI ko events bhejta, isliye band.
set_tracing_disabled(True)

HERE = Path(__file__).resolve().parent
MEMORY_SERVER = HERE / "servers" / "memory_server.py"
MARKET_SERVER = HERE / "servers" / "market_server.py"
MEMORY_JSON = HERE / "output" / "memory.json"
QUOTES_JSON = HERE / "output" / "market_quotes.json"


# Groq ke rate limits PER-MODEL hote hain — ek model ka daily token quota
# khatam ho jaye to doosre model par switch karke lab phir bhi chal jaati hai.
MODEL_CHAIN = [
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.1-8b-instant",
]


def groq_model(name: str = "llama-3.3-70b-versatile") -> OpenAIChatCompletionsModel:
    """Groq ka OpenAI-compatible endpoint — Agents SDK isse normal model samajhta hai."""
    client = AsyncOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
    )
    return OpenAIChatCompletionsModel(model=name, openai_client=client)


def print_tool_traffic(result) -> None:
    """
    Runner.run ke result.new_items me poora run-trail hota hai —
    tool CALLS (LLM ne kya maanga) aur tool OUTPUTS (MCP server ne kya lautaya).
    Yahi 'wire traffic' dekhna MCP samajhne ka sabse accha tareeka hai.
    """
    for item in result.new_items:
        kind = getattr(item, "type", "")
        if kind == "tool_call_item":
            raw = item.raw_item
            name = getattr(raw, "name", "?")
            args = getattr(raw, "arguments", "")
            print(f"   [TOOL CALL ] {name}({args})")
        elif kind == "tool_call_output_item":
            out = str(item.output)
            if len(out) > 220:
                out = out[:220] + " ...<truncated>"
            print(f"   [TOOL REPLY] {out}")


async def run_with_retry(agent: Agent, prompt: str, attempts: int = 4):
    """
    Free Groq tier kabhi-kabhi 429/5xx deta hai — retry wrapper.
    Rate-limit (429) par MODEL_CHAIN ka agla model try karte hain, kyunki Groq
    par har model ka APNA alag daily token quota hota hai.
    """
    last_err = None
    model_idx = 0
    for i in range(1, attempts + 1):
        try:
            return await Runner.run(agent, prompt)
        except Exception as e:  # noqa: BLE001 — transient API errors pakdo
            last_err = e
            msg = str(e)
            print(f"   (attempt {i}/{attempts} fail: {type(e).__name__}: {msg[:140]}...)")
            if "rate_limit" in msg or "429" in msg:
                if model_idx + 1 < len(MODEL_CHAIN):
                    model_idx += 1
                    print(f"   (quota khatam — fallback model: {MODEL_CHAIN[model_idx]})")
                    agent.model = groq_model(MODEL_CHAIN[model_idx])
            await asyncio.sleep(3 * i)
    raise last_err


async def main() -> None:
    print("=" * 70)
    print("LAB 3: Ek agent + DO MCP servers (memory + market) — stdio subprocesses")
    print("=" * 70)

    # FRESH START: purani files hata do taaki har run ka demo deterministic ho.
    # (Persistence ka asli demo TASK 1 -> TASK 2 ke beech hai — do ALAG
    # Runner.run calls, ek hi disk file. Run-to-run persistence bhi kaam karti
    # hai, bas demo output clean rakhne ke liye yahan reset kar rahe hain.)
    for f in (MEMORY_JSON, QUOTES_JSON):
        if f.exists():
            f.unlink()
            print(f"[RESET] purani {f.name} delete ki (clean demo ke liye)")

    # Har server ke launch params — client 'uv run <server.py>' subprocess
    # spawn karega aur stdin/stdout par MCP (JSON-RPC) bolega.
    memory_params = {"command": "uv", "args": ["run", str(MEMORY_SERVER)]}
    market_params = {"command": "uv", "args": ["run", str(MARKET_SERVER)]}

    # DONO servers ek saath kholo — nested async with (chaaho to
    # contextlib.AsyncExitStack bhi chalega). Har 'async with' ek subprocess
    # start karta hai + MCP initialize handshake karta hai.
    async with MCPServerStdio(
        params=memory_params, client_session_timeout_seconds=60, name="memory"
    ) as memory_server:
        async with MCPServerStdio(
            params=market_params, client_session_timeout_seconds=60, name="market"
        ) as market_server:

            # TOOL DISCOVERY: list_tools() = MCP ka 'tools/list' request.
            # Dekho — dono ALAG processes apne-apne tools advertise kar rahe.
            for srv in (memory_server, market_server):
                tools = await srv.list_tools()
                print(f"\n[DISCOVERY] server '{srv.name}' ke tools:")
                for t in tools:
                    print(f"   - {t.name}: {t.description}")

            # EK agent, DO servers: Agents SDK dono ki tool-lists merge karke
            # LLM ko deta hai. Agent ke liye sab tools barabar hain.
            agent = Agent(
                name="investment_researcher",
                instructions=(
                    "You are an investment researcher. You have market data tools "
                    "(get_price, get_prices, market_summary) and memory tools "
                    "(save_memory, recall_memories, list_entities). "
                    "Use tools for facts. NEVER invent or round prices — always "
                    "copy the exact numbers from tool results. "
                    "When asked to remember something, use save_memory; when asked "
                    "what you remember, use recall_memories. Do not repeat the "
                    "same tool call twice. Reply concisely."
                ),
                model=groq_model(),
                mcp_servers=[memory_server, market_server],  # <-- multiple servers!
            )

            # ---------------- TASK 1: research + memory me likho ----------------
            print("\n" + "-" * 70)
            print("TASK 1: prices dekho, sabse sasta dhundo, fact memory me save karo")
            print("-" * 70)
            task1 = (
                "AAPL, TSLA aur MSFT ke aaj ke prices dekho (get_prices use karo). "
                "Jo sabse SASTA (cheapest) ho, uske baare me ek chhota fact "
                "save_memory se entity 'watchlist' ke under save karo — fact me "
                "symbol aur exact price dono likhna. Phir mujhe teeno prices aur "
                "cheapest pick batao."
            )
            result1 = await run_with_retry(agent, task1)
            print_tool_traffic(result1)
            print(f"\n[AGENT FINAL] {result1.final_output}")

            # ------------- TASK 2: NAYA Runner.run = NAYI conversation -------------
            # LLM ke paas Task 1 ka koi chat-history context NAHI hai. Agar fact
            # wapas mila, to wo MCP memory server (disk) se aaya — yahi
            # persistence-across-calls ka proof hai.
            print("\n" + "-" * 70)
            print("TASK 2 (fresh Runner.run — koi shared chat history nahi):")
            print("-" * 70)
            task2 = (
                "Tumhe 'watchlist' ke baare me kya yaad hai? recall_memories tool "
                "se check karke jo bhi saved facts hain wo mujhe batao."
            )
            result2 = await run_with_retry(agent, task2)
            print_tool_traffic(result2)
            print(f"\n[AGENT FINAL] {result2.final_output}")

    # ---------------- VERIFICATION: files genuinely bani? ----------------
    print("\n" + "=" * 70)
    print("VERIFY: dono JSON files disk par bani ya nahi")
    print("=" * 70)
    for f in (MEMORY_JSON, QUOTES_JSON):
        if f.exists():
            data = json.loads(f.read_text())
            print(f"[OK] {f.name} exists — preview: {json.dumps(data)[:200]}...")
        else:
            print(f"[FAIL] {f.name} NAHI bani!")

    if MEMORY_JSON.exists():
        store = json.loads(MEMORY_JSON.read_text())
        facts = [x["fact"] for x in store.get("watchlist", [])]
        print(f"\n'watchlist' ke saved facts ({len(facts)}): {facts}")

    print(
        "\nTAKEAWAY: Ek agent, do alag MCP server processes — tools seamlessly "
        "merge ho gaye, aur memory DISK par hone se naye Runner.run call me bhi "
        "fact wapas mil gaya. Course me yahi pattern Brave/Polygon/memory "
        "servers ke saath hota hai — bas wo remote APIs call karte hain."
    )


if __name__ == "__main__":
    asyncio.run(main())
