"""
LAB 4 — GRAND CAPSTONE: AGENT TRADING FLOOR (Lectures L122-L127)
=================================================================

KYA SEEKHENGE (course ka FINAL project, free version)
-----------------------------------------------------
Ed Donner ke course me ye capstone aisa hai (L122-L127):
  - 4 AUTONOMOUS TRADER AGENTS, har ek ek legendary investor ke naam par:
      * Warren  -> Warren Buffett style  : VALUE investing (moats, margin of safety)
      * George  -> George Soros style    : MACRO / CONTRARIAN bets (trend ke khilaf)
      * Ray     -> Ray Dalio style       : SYSTEMATIC / risk-parity diversification
      * Cathie  -> Cathie Wood style     : GROWTH / disruptive innovation / crypto
  - Har trader ek SCHEDULER par HAR FEW MINUTES chalta hai (infinite loop +
    sleep) aur MCP servers ke through AUTONOMOUSLY trade karta hai:
      accounts server (balance/buy/sell) + market server (Polygon.io PAID API)
      + research server (Brave Search PAID API + fetch) + memory server (libsql)
      + push notification server.
  - Yahi "agent ko REAL tools + REAL paisa (simulated) + REAL autonomy" wala
    climax hai — LLM khud decide karta hai kya kharidna/bechna hai.

HUMARA FREE VERSION — SAME ARCHITECTURE, ZERO PAID APIs:
  - 3 trader personas (Warren-value, Cathie-growth, Ray-systematic) —
    George ko skip kiya (free Groq rate limits me 3 hi sahi); concept comments
    me uska zikr upar ho gaya.
  - Market data: Lab 3 ka SIMULATED market_server.py (Polygon ki jagah).
  - Accounts: Lab 2 ka accounts_server.py (persistent JSON-backed).
  - Scheduler NAHI — EK SINGLE ROUND chalate hain. Production me ye loop
    hota: `while True: run_all_traders(); sleep(n_minutes)` ya cron/APScheduler
    — har round me trader market re-check karke REBALANCE karta hai.
  - Research/memory/push servers skip — core idea (multi-MCP-server agent
    autonomy) 2 servers se hi crystal-clear ho jata hai.

ARCHITECTURE (host/client/server recap):
  lab4 (HOST process)
    |-- MCPServerStdio #1 --spawn--> uv run servers/accounts_server.py (stdio JSON-RPC)
    |-- MCPServerStdio #2 --spawn--> uv run servers/market_server.py   (stdio JSON-RPC)
    |-- 3 x Agent (Groq llama-3.3-70b), HAR agent ko DONO servers ke tools
        milte hain: mcp_servers=[accounts, market] — Agents SDK har turn par
        dono servers ke tools/list ko merge karke LLM ko deta hai. LLM ko
        pata bhi nahi hota kaunsa tool kis server/process se aa raha hai!

EK IMPORTANT SIMULATION QUIRK (course me bhi aisa hi tha, samajh lo):
  market_server QUOTES deta hai (research ke liye, Polygon-jaisa simulated),
  par TRADE EXECUTION accounts_server apne internal fixed price list se karta
  hai (sirf AAPL/TSLA/GOOGL/MSFT tradeable). Production me dono ek hi price
  source share karte. Iska side-effect: Day-0 par P&L ~ $0 hota hai kyunki
  buy-price == valuation-price (koi market move hua hi nahi abhi).

DISCLAIMER: Ye PURELY EDUCATIONAL SIMULATION hai — fake paisa, fake prices,
fake market. Ye real trading/investment advice NAHI hai. LLMs ko real paise
ke saath autonomous trading mat karne dena!

KAISE CHALANA:
  cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
  uv run Udemy_EdDonner_Course/Week6_MCP/Practical/lab4_trading_floor.py

OUTPUT: console par har trader ke tool-calls + decisions, aur end me
Practical/output/trading_report.md me TRADING FLOOR REPORT.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from agents import Agent, OpenAIChatCompletionsModel, Runner, set_tracing_disabled
from agents.mcp import MCPServerStdio

# ---------------------------------------------------------------------------
# PATHS — sab __file__ ke relative (cwd pe bharosa nahi, MCP subprocess
# spawning ke liye bhi ABSOLUTE paths chahiye).
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
SERVERS_DIR = HERE / "servers"
OUTPUT_DIR = HERE / "output"
ACCOUNTS_JSON = OUTPUT_DIR / "accounts.json"   # accounts_server ki persistent state
REPORT_PATH = OUTPUT_DIR / "trading_report.md"

# Report/reset ke liye hum accounts.py ko DIRECTLY import karte hain (HOST
# side se MCP bypass) — yahi to separation ka faayda hai: business logic
# MCP-agnostic hai, to host bhi use seedha use kar sakta hai. Valuation
# wahi fixed prices use karegi jo execution ne kiye the (consistent P&L).
sys.path.insert(0, str(SERVERS_DIR))
import accounts as accounts_logic  # noqa: E402  (servers/accounts.py)

load_dotenv(override=True)
set_tracing_disabled(True)  # OPENAI_API_KEY invalid hai — tracing OFF zaroori

SEED_CASH = 10_000.0
TRADEABLE = "AAPL, TSLA, GOOGL, MSFT"  # accounts_server sirf inhe execute karta hai


def groq_model(name: str = "llama-3.3-70b-versatile") -> OpenAIChatCompletionsModel:
    """Groq ka OpenAI-compatible endpoint -> Agents SDK ka model object."""
    import os
    client = AsyncOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
    )
    return OpenAIChatCompletionsModel(model=name, openai_client=client)


# ---------------------------------------------------------------------------
# TRADER PERSONAS — har trader ka apna Agent banega, instructions me uski
# investing PHILOSOPHY baked-in hai. Yahi course ka trick hai: SAME tools,
# ALAG system prompts => genuinely alag trading behaviour.
# ---------------------------------------------------------------------------
TRADERS = [
    {
        "name": "Warren",
        "title": "Value Investor (Warren Buffett style)",
        "strategy": (
            "Tum ek VALUE investor ho, Warren Buffett ki philosophy: wonderful "
            "businesses at fair prices, durable competitive moats, margin of "
            "safety. Hype aur volatility se door raho. Sabse SASTE, sabse "
            "stable franchises pasand karo. Thoda cash reserve rakhna achhi "
            "baat hai — 'be fearful when others are greedy'."
        ),
    },
    {
        "name": "Cathie",
        "title": "Growth Investor (Cathie Wood style)",
        "strategy": (
            "Tum ek GROWTH / disruptive-innovation investor ho, Cathie Wood ki "
            "philosophy: exponential technologies (EV, AI, robotics) me high-"
            "conviction bets. Volatility = opportunity. Boring value stocks "
            "tumhe pasand NAHI — sabse zyada disruption potential wali cheez "
            "me aggressively invest karo."
        ),
    },
    {
        "name": "Ray",
        "title": "Systematic Macro (Ray Dalio style)",
        "strategy": (
            "Tum ek SYSTEMATIC macro investor ho, Ray Dalio ki philosophy: "
            "diversification hi 'holy grail' hai. Kabhi bhi sab paisa ek "
            "asset me nahi — apne 2 trades ALAG-ALAG companies/sectors me "
            "baanto, position sizes balanced rakho, aur meaningful cash "
            "buffer maintain karo."
        ),
    },
]


def build_instructions(trader: dict) -> str:
    """Persona + trading-floor ke ground rules => agent ka system prompt."""
    return (
        f"You are {trader['name']}, an autonomous trading agent on an AI "
        f"trading floor. {trader['strategy']}\n\n"
        "GROUND RULES:\n"
        f"- Tumhara account name exactly '{trader['name']}' hai — har accounts "
        "tool call me yahi name use karo.\n"
        f"- Sirf ye symbols TRADEABLE hain: {TRADEABLE}. Market server ke "
        "quotes RESEARCH ke liye hain; actual execution price ke liye "
        "accounts server ka lookup_share_price dekho.\n"
        "- AT MOST 2 trades (buy_shares/sell_shares calls). Apne cash se "
        "zyada kabhi mat kharido.\n"
        "- Tools ke results ka intezar karke hi agla step lo. Final answer "
        "short English me do."
    )


# Har trader ko SAME task milta hai — behaviour ka difference instructions
# (persona) se aata hai, prompt se nahi.
ROUND_PROMPT = (
    "Aaj ka trading round shuru karo. Follow these steps:\n"
    "1) get_balance se apna cash check karo. Agar 0 hai to deposit tool se "
    f"exactly {SEED_CASH:.0f} USD seed capital deposit karo.\n"
    "2) market_summary aur lookup_share_price tools se prices research karo.\n"
    "3) Apni strategy ke hisab se AT MOST 2 successful trades execute karo "
    "(buy_shares / sell_shares). IMPORTANT: buy se pehle khud calculate karo "
    "ki price x quantity tumhare cash balance se KAM ho. Agar koi trade "
    "reject ho jaye to usi trade ko CHHOTI quantity ke saath ek baar retry "
    "kar sakte ho. Jo shares tumhare paas nahi hain unhe sell mat karo.\n"
    "4) get_portfolio se final position confirm karo.\n"
    "5) Apne final answer ki LAST LINE exactly is format me do:\n"
    "RATIONALE: <one sentence — sirf SUCCESSFUL trades mention karo jo tool "
    "outputs se confirm hue; koi trade nahi hua to honestly wahi bolo>"
)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
# Free Groq tier par 429 (rate limit) common hai — do bachav:
#   1. RETRY + BACKOFF (25s, 50s) — TPM window reset hone ka time do
#   2. MODEL FALLBACK — 8b-instant ka rate-limit BUCKET alag hota hai,
#      to 70b chocked ho to chhota model floor ko zinda rakhta hai
MODEL_CHAIN = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]


async def run_trader(trader: dict, mcp_servers: list, attempts: int = 3):
    """Trader ka round chalao: model chain + retry/backoff ke saath.
    Return: (RunResult, model_name_jo_chala)."""
    last_err: Exception = RuntimeError("no attempt made")
    for model_name in MODEL_CHAIN:
        # Har model ke liye FRESH agent — same persona, same MCP servers.
        agent = Agent(
            name=f"{trader['name']}_trader",
            instructions=build_instructions(trader),
            model=groq_model(model_name),
            mcp_servers=mcp_servers,
        )
        for attempt in range(1, attempts + 1):
            try:
                result = await Runner.run(agent, ROUND_PROMPT, max_turns=15)
                return result, model_name
            except Exception as e:  # noqa: BLE001 — demo me broad catch theek hai
                last_err = e
                print(
                    f"   [{model_name} retry {attempt}/{attempts}] "
                    f"{type(e).__name__}: {str(e)[:120]}"
                )
                if attempt < attempts:
                    await asyncio.sleep(25 * attempt)  # backoff: 25s, 50s
        print(f"   [fallback] {model_name} exhausted — switching model")
    raise last_err


def print_tool_activity(result) -> int:
    """RunResult.new_items me se tool calls/outputs nikal kar print karo —
    yahi 'agent ne MCP par kya kiya' ka live trace hai. Count return karta hai."""
    calls = 0
    for item in result.new_items:
        kind = getattr(item, "type", "")
        if kind == "tool_call_item":
            raw = item.raw_item
            name = getattr(raw, "name", "?")
            args = getattr(raw, "arguments", "")
            print(f"   TOOL CALL -> {name}({args})")
            calls += 1
        elif kind == "tool_call_output_item":
            out = str(getattr(item, "output", "")).replace("\n", " ")[:150]
            print(f"   TOOL OUT  <- {out}")
    return calls


def extract_rationale(final_output: str) -> str:
    """Final answer me se 'RATIONALE:' wali line nikalo (graceful fallback)."""
    if not final_output:
        return "(no rationale provided)"
    for line in reversed(final_output.strip().splitlines()):
        if "RATIONALE" in line.upper():
            return line.split(":", 1)[-1].strip() if ":" in line else line.strip()
    # Format follow nahi kiya to last non-empty line hi sahi
    lines = [l.strip() for l in final_output.strip().splitlines() if l.strip()]
    return lines[-1] if lines else "(no rationale provided)"


def build_report(snapshots: dict[str, dict], rationales: dict[str, str]) -> str:
    """Har trader ke (round ke turant baad liye gaye) snapshot se markdown
    report banao. Snapshot isliye — accounts.json SHARED file hai (lab2/lab3
    bhi isi me likhte hain); round ke turant baad state capture karna report
    ko race-conditions se bachata hai. Production lesson: whole-file JSON
    rewrite multi-writer ke liye nahi hota — wahan SQLite/Postgres +
    transactions chahiye."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    md = [
        "# TRADING FLOOR REPORT",
        "",
        f"_Generated: {now} | Round: 1 (single round — production me scheduler "
        "har few minutes me naya round chalata)_",
        "",
        "> **DISCLAIMER**: Educational simulation only — fake money, simulated "
        "prices. This is NOT real trading or investment advice.",
        "",
    ]
    for trader in TRADERS:
        name = trader["name"]
        summary = snapshots.get(name) or accounts_logic.Account.get(name).summary()
        holdings = summary["holdings"]
        md.append(f"## {name} — {trader['title']}")
        md.append("")
        if holdings:
            md.append("| Holding | Qty | Price | Value |")
            md.append("|---------|----:|------:|------:|")
            for sym, qty in holdings.items():
                price = accounts_logic.get_share_price(sym)
                md.append(f"| {sym} | {qty} | ${price:,.2f} | ${price * qty:,.2f} |")
        else:
            md.append("_(no holdings — is round me trade nahi kiya / cash only)_")
        md.append("")
        md.append(f"- **Cash**: ${summary['cash_balance']:,.2f}")
        md.append(f"- **Portfolio value**: ${summary['portfolio_value']:,.2f}")
        md.append(
            f"- **P&L**: ${summary['profit_loss']:,.2f} "
            f"(vs ${summary['total_deposits']:,.2f} deposited)"
        )
        md.append(f"- **Rationale**: {rationales.get(name, '(agent run failed)')}")
        md.append("")
    md.append(
        "_Note: Day-0 P&L ~$0 expected hai — execution aur valuation same fixed "
        "prices use karte hain; real system me agle rounds tak market move hone "
        "se P&L banta._"
    )
    md.append("")
    return "\n".join(md)


# ---------------------------------------------------------------------------
# MAIN — trading floor ka ek round
# ---------------------------------------------------------------------------
async def main() -> None:
    print("=" * 70)
    print("AGENT TRADING FLOOR — capstone (free version, single round)")
    print("=" * 70)

    # Fresh trading day: SIRF apne 3 trader accounts reset karo —
    # accounts.json me lab2 ke doosre accounts (ashish/ed) ko mat chhedo.
    for trader in TRADERS:
        accounts_logic.reset_account(trader["name"])
    print(f"[setup] {len(TRADERS)} trader accounts reset (fresh ${SEED_CASH:,.0f} seed round)\n")

    accounts_params = {"command": "uv", "args": ["run", str(SERVERS_DIR / "accounts_server.py")]}
    market_params = {"command": "uv", "args": ["run", str(SERVERS_DIR / "market_server.py")]}

    # DONO MCP servers ek saath kholo — nested async with = dono subprocess
    # zinda rehte hain pura round. (3+ servers ho to contextlib.AsyncExitStack
    # zyada clean rehta hai.)
    async with MCPServerStdio(
        params=accounts_params, client_session_timeout_seconds=60, name="accounts"
    ) as accounts_srv, MCPServerStdio(
        params=market_params, client_session_timeout_seconds=60, name="market"
    ) as market_srv:
        # TOOL DISCOVERY — client har server se tools/list poochta hai; yahi
        # merged list LLM ko milti hai. Print karke dekho dono ka contribution.
        for srv in (accounts_srv, market_srv):
            tools = await srv.list_tools()
            print(f"[discovery] {srv.name} server tools: {[t.name for t in tools]}")
        print()

        rationales: dict[str, str] = {}
        snapshots: dict[str, dict] = {}
        for i, trader in enumerate(TRADERS):
            print("-" * 70)
            print(f"TRADER {i + 1}/{len(TRADERS)}: {trader['name']} — {trader['title']}")
            print("-" * 70)
            try:
                # Har trader ka APNA agent banta hai (run_trader ke andar) —
                # same MCP servers, alag persona instructions.
                result, used_model = await run_trader(trader, [accounts_srv, market_srv])
                n_calls = print_tool_activity(result)
                print(f"\n   {trader['name']} ka final answer ({n_calls} tool calls, model={used_model}):")
                print("   " + str(result.final_output).replace("\n", "\n   "))
                rationales[trader["name"]] = extract_rationale(str(result.final_output))
            except Exception as e:  # noqa: BLE001 — ek trader fail ho to floor mat giraao
                print(f"   !! {trader['name']} round FAILED: {type(e).__name__}: {str(e)[:160]}")
                rationales[trader["name"]] = f"(round failed: {type(e).__name__})"
            # Round ke TURANT BAAD state snapshot lo (report ke liye) —
            # shared accounts.json me doosre labs ka interference avoid hota hai.
            snapshots[trader["name"]] = accounts_logic.Account.get(trader["name"]).summary()
            print()
            # SEQUENTIAL execution — free Groq tier ke rate limits (TPM) ke
            # liye. Paid tier par asyncio.gather(*[Runner.run(...) ...]) se
            # teeno traders PARALLEL chal sakte hain (course me bhi parallel
            # + scheduler hai). Beech me chhota gap aur de do:
            if i < len(TRADERS) - 1:
                await asyncio.sleep(15)

    # Servers band (subprocesses exit) — ab REPORT banao snapshots se.
    report = build_report(snapshots, rationales)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report)
    print("=" * 70)
    print(f"REPORT saved -> {REPORT_PATH}")
    print("=" * 70)
    print(report)


if __name__ == "__main__":
    asyncio.run(main())
