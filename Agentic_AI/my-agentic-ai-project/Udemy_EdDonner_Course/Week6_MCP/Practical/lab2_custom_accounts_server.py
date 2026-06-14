"""
LAB 2 — Apna BUSINESS MCP Server: Accounts (Lectures L114-L117)
================================================================

Is lab me kya seekhenge:
  1. BUSINESS LOGIC -> MCP (L114-L115) — Week-3 engineering-team capstone
     wali Account class (course bhi wahi reuse karta hai) ko FastMCP tools
     ke peeche lagana. Files: servers/accounts.py (logic, JSON persistence)
     + servers/accounts_server.py (thin @mcp.tool() wrapper).
  2. TOOLS DISCOVERY (L116)         — MCPServerStdio se server subprocess
     launch karke list_tools() — LLM ko jo schema dikhta hai wahi print
     karenge. Dekho ki server-side docstrings hi tool descriptions ban gayin.
  3. AGENT + MCP SERVER (L117)      — Agents SDK Agent ko mcp_servers=[...]
     dena. Bas! SDK har turn pe MCP tools ko function-tools ki tarah LLM ko
     pesh karta hai aur tool-call loop khud chalata hai.
  4. STATE VERIFICATION             — Agent ke tool calls ke baad hum KHUD
     output/accounts.json padhke prove karenge ki real side-effects hue —
     LLM ki baaton pe nahi, DISK pe bharosa.

Kaise chalana hai:
  cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
  uv run Udemy_EdDonner_Course/Week6_MCP/Practical/lab2_custom_accounts_server.py

LLM: Groq (free) — llama-3.3-70b-versatile. OPENAI_API_KEY invalid hai
isliye tracing disabled (Week-2 labs wala hi pattern).
"""

import os
import json
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, set_tracing_disabled
from agents.mcp import MCPServerStdio

load_dotenv(override=True)
set_tracing_disabled(True)  # OPENAI_API_KEY invalid — warna 401 spam

# ---------------------------------------------------------------------------
# Paths — sab __file__ ke relative compute (cwd pe bharosa nahi).
# SERVER_PATH ABSOLUTE hona zaroori hai: MCP client 'uv run <path>' se ek
# NAYA subprocess spawn karega jiska cwd kuch bhi ho sakta hai.
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
SERVER_PATH = HERE / "servers" / "accounts_server.py"
ACCOUNTS_JSON = HERE / "output" / "accounts.json"

GROQ_MODEL = "llama-3.3-70b-versatile"

# Groq free tier me TPD (tokens-per-day) limit PER-MODEL hoti hai — agar 70b
# ka daily quota khatam ho jaye to doosre models pe apna alag quota bacha
# hota hai. Isliye sleep-retry ke saath-saath MODEL FALLBACK chain bhi rakhi
# hai (sab tool-calling support karte hain):
FALLBACK_MODELS = [
    GROQ_MODEL,
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.1-8b-instant",
]


def groq_model(name: str = GROQ_MODEL) -> OpenAIChatCompletionsModel:
    """Groq ko Agents SDK me plug karne ka standard adapter (Week-2 wala)."""
    client = AsyncOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
    )
    return OpenAIChatCompletionsModel(model=name, openai_client=client)


async def run_with_retry(agent: Agent, prompt: str, attempts: int = 3):
    """Free Groq tier kabhi-kabhi rate-limit/transient error deta hai.
    Strategy: har model pe try karo; 429 (daily quota) aaye to AGLE model
    pe fallback; transient error aaye to chhota sleep + retry."""
    last_err = None
    for model_name in FALLBACK_MODELS:
        agent.model = groq_model(model_name)  # model swap, agent wahi
        for i in range(1, attempts + 1):
            try:
                return await Runner.run(agent, prompt, max_turns=15)
            except Exception as e:
                last_err = e
                msg = str(e)
                print(f"  [{model_name} | try {i}/{attempts}] {type(e).__name__}: {msg[:120]}")
                if "rate_limit" in msg or "429" in msg:
                    break  # daily quota — sleep se nahi sudhrega, next model
                if i < attempts:
                    await asyncio.sleep(5 * i)
    raise last_err


def print_tool_calls(result) -> None:
    """RunResult.new_items me se tool calls nikaal ke dikhana — proof ki
    LLM ne sach me MCP tools use kiye (sirf haath nahi hilaya)."""
    print("\n--- TOOL CALLS (agent ne MCP server pe kya-kya chalaya) ---")
    n = 0
    for item in result.new_items:
        if item.type == "tool_call_item":
            n += 1
            raw = item.raw_item
            name = getattr(raw, "name", "?")
            args = getattr(raw, "arguments", "")
            print(f"  {n}. {name}({args})")
        elif item.type == "tool_call_output_item":
            out = str(item.output)
            print(f"     -> {out[:120]}{'...' if len(out) > 120 else ''}")
    if n == 0:
        print("  (koi tool call nahi hua — kuch gadbad hai!)")


async def main() -> None:
    print("=" * 70)
    print("LAB 2 — Custom Accounts MCP Server (L114-L117)")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # STEP 0: Idempotent demo — Ashish ka account reset karo taaki har run
    # pe same starting point ho (warna re-run pe 10000 + 10000 ho jata).
    # Persistence ka asli fayda lab4 me dikhega jab trader isi JSON ko
    # padhega — yahan hum bas clean-slate demo chahte hain.
    # -----------------------------------------------------------------------
    import sys
    sys.path.insert(0, str(HERE / "servers"))  # accounts.py import ke liye
    from accounts import reset_account

    reset_account("Ashish")
    print(f"\n[setup] 'Ashish' account reset kiya: {ACCOUNTS_JSON}")

    # -----------------------------------------------------------------------
    # STEP 1: MCP server ko stdio subprocess ki tarah launch karo.
    # 'async with' ke andar: subprocess spawn -> initialize handshake ->
    # session ready. Bahar nikalte hi subprocess saaf-suthra band.
    # -----------------------------------------------------------------------
    params = {"command": "uv", "args": ["run", str(SERVER_PATH)]}
    async with MCPServerStdio(
        params=params, client_session_timeout_seconds=60
    ) as server:
        # -------------------------------------------------------------------
        # STEP 2: TOOLS DISCOVERY — yahi list LLM ko har turn dikhayi jaati
        # hai. Dekho: descriptions == accounts_server.py ki docstrings!
        # -------------------------------------------------------------------
        tools = await server.list_tools()
        print(f"\n--- DISCOVERY: server ne {len(tools)} tools advertise kiye ---")
        for t in tools:
            desc = (t.description or "").split("\n")[0]
            print(f"  * {t.name:20s} — {desc}")

        # -------------------------------------------------------------------
        # STEP 3: Agent banao aur MCP server attach karo. mcp_servers=[...]
        # ke alawa KUCH NAHI badla Week-2 ke agents se — yahi MCP ka point
        # hai: tools kahin bhi hon (alag process/language/machine), agent
        # code same rehta hai.
        # -------------------------------------------------------------------
        instructions = (
            "You are a precise account manager. You manage trading accounts "
            "using the provided tools. ALWAYS use tools for every account "
            "action — never make up balances. After completing the requested "
            "actions, call get_portfolio and present a short final summary."
        )
        agent = Agent(
            name="AccountManager",
            instructions=instructions,
            model=groq_model(),
            mcp_servers=[server],
        )

        task = (
            "Ashish ke account me 10000 USD deposit karo, phir 5 AAPL shares "
            "aur 3 TSLA shares kharido, phir portfolio summary do."
        )
        print(f"\n--- AGENT TASK ---\n  {task}")
        print("\n[run] Groq llama-3.3-70b agent chal raha hai (MCP tools ke saath)...")

        result = await run_with_retry(agent, task)

        print_tool_calls(result)

        print("\n--- AGENT FINAL ANSWER ---")
        print(result.final_output)

        # -------------------------------------------------------------------
        # STEP 4 (bonus): RESOURCE read — tools nahi, data endpoint.
        # Agents SDK primarily tools use karta hai, par underlying MCP
        # session se hum resource bhi padh sakte hain (host-controlled data).
        # -------------------------------------------------------------------
        try:
            res = await server.session.read_resource("accounts://report/Ashish")
            print("\n--- MCP RESOURCE accounts://report/Ashish ---")
            for content in res.contents:
                print(getattr(content, "text", content))
        except Exception as e:
            print(f"\n[resource read skip] {type(e).__name__}: {e}")

    # ------------------------------------------------------------------------
    # STEP 5: GROUND TRUTH — server subprocess band ho chuka hai, ab disk
    # pe jo JSON bacha hai wahi sach hai. Expected: balance = 10000 -
    # 5*150 - 3*250 = 8500; holdings = {AAPL: 5, TSLA: 3}.
    # -----------------------------------------------------------------------
    print("\n--- VERIFICATION: output/accounts.json (disk pe real state) ---")
    state = json.loads(ACCOUNTS_JSON.read_text())
    print(json.dumps(state.get("ashish"), indent=2))

    ashish = state.get("ashish", {})
    ok = (
        ashish.get("balance") == 8500.0
        and ashish.get("holdings", {}).get("AAPL") == 5
        and ashish.get("holdings", {}).get("TSLA") == 3
    )
    print(f"\n[verify] balance==8500 & 5 AAPL & 3 TSLA on disk: {'PASS' if ok else 'FAIL'}")
    print("\nDone! Persistence ki wajah se ye state lab4 (trader) reuse karega.")


if __name__ == "__main__":
    asyncio.run(main())
