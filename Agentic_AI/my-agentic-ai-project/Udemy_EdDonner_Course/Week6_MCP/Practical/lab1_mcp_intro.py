"""
LAB 1 — MCP Intro: Concepts + Pehla MCP Server (Lectures L108-L113)
====================================================================

Is lab me kya seekhenge:
  1. MCP CONCEPTS (L108-L110)  — MCP kya hai, kya NAHI hai; Host/Client/Server
                                 architecture; stdio vs SSE/HTTP transports.
  2. DIRECT CLIENT (L111)      — Bina kisi agent framework ke, raw `mcp`
                                 library ke ClientSession se server connect
                                 karke tools LIST + CALL karna (protocol ko
                                 nanga dekhna).
  3. AGENTS SDK ROUTE (L112)   — MCPServerStdio + Agent(mcp_servers=[...]) —
                                 ab LLM (Groq) khud decide karta hai kaunsa
                                 MCP tool call karna hai.
  4. MARKETPLACE + SECURITY (L113) — comment block niche dekho.

Kaise chalana hai:
  cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
  uv run Udemy_EdDonner_Course/Week6_MCP/Practical/lab1_mcp_intro.py

LLM: Groq (free) — llama-3.3-70b-versatile. OpenAI tracing disabled
(OPENAI_API_KEY invalid hai, aur hume zaroorat bhi nahi).
"""

import os
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import Agent, Runner, OpenAIChatCompletionsModel, set_tracing_disabled
from agents.mcp import MCPServerStdio

# Direct (raw) MCP client ke imports — ye `mcp` package se aate hain,
# Agents SDK se nahi. Yahi package FastMCP server bhi deta hai.
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv(override=True)
set_tracing_disabled(True)

# ---------------------------------------------------------------------------
# CONCEPT 1 (L108-L109): MCP = "USB-C of Agentic AI"
#
# MCP (Model Context Protocol) — Anthropic ka banaya hua OPEN PROTOCOL.
# Dhyan se: ye FRAMEWORK nahi hai (CrewAI/LangGraph jaisa), AGENT bhi nahi
# hai. Ye sirf ek STANDARD hai jo define karta hai ki LLM-apps ko external
# TOOLS, RESOURCES aur PROMPTS se kaise connect kiya jaaye.
#
# USB-C analogy kyun? Pehle har laptop/phone ka apna charger hota tha.
# USB-C ne ek standard plug bana diya — koi bhi device, koi bhi charger.
# Waise hi MCP se pehle: har framework ke liye har tool ka alag integration
# likhna padta tha (N frameworks x M tools = N*M adapters). MCP ke baad:
# tool-maker EK BAAR MCP server banata hai, aur HAR MCP-capable host
# (Claude Desktop, Cursor, OpenAI Agents SDK, ...) use plug-and-play
# use kar sakta hai. N + M, multiply nahi.
#
# ARCHITECTURE — 3 roles (L110):
#
#   HOST  ──contains──>  MCP CLIENT  ──1:1 connection──>  MCP SERVER
#
#   - HOST   = hamari application / agent runtime (ye script, ya Claude
#              Desktop, ya Cursor). User-facing cheez.
#   - CLIENT = host ke ANDAR ek object, har server ke liye EK dedicated
#              client (1-per-server). Ye protocol-level baatein karta hai:
#              initialize handshake, tools/list, tools/call.
#   - SERVER = wo process jo actual tools/resources expose karta hai
#              (hamara greeter_server.py). Server ko pata bhi nahi hota
#              ki use kaun sa LLM use kar raha hai — full decoupling.
#
# TRANSPORTS:
#   - stdio   : host server ko LOCAL SUBPROCESS ke roop me spawn karta hai;
#               JSON-RPC messages stdin/stdout par chalti hain. Aaj hum
#               yahi use kar rahe hain — process spawn hota hua dikhega.
#   - SSE/HTTP: server kahin REMOTE machine pe chal raha hai, host HTTP
#               (Server-Sent Events / streamable HTTP) se baat karta hai.
#               Concept same, sirf pipe alag.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# CONCEPT 2 (L113): MARKETPLACE + SECURITY NOTE
#
# Course me Ed marketplace ke ready-made servers use karte hain — e.g.
# `npx @modelcontextprotocol/server-fetch` (web fetch) ya playwright
# (browser automation). Ye sab NODE/NPX par chalte hain. Hamare setup me
# node ki guarantee nahi hai, isliye humne APNA Python FastMCP server
# banaya (servers/greeter_server.py) — concept bilkul same hai, bas
# `npx ...` ki jagah `uv run ...` command se spawn hota hai.
#
# SECURITY (L113 — bahut important): MCP server install karna = us machine
# par THIRD-PARTY CODE chalana. Ye classic SUPPLY-CHAIN RISK hai:
#   - malicious server tumhare files padh/likh sakta hai, env vars
#     (API keys!) chura sakta hai,
#   - "tool poisoning": tool ke description me hidden instructions daalkar
#     LLM ko manipulate kiya ja sakta hai.
# Rule: sirf TRUSTED sources (official repos, verified publishers) ke
# servers use karo, code skim karo, aur least-privilege me chalao.
# ---------------------------------------------------------------------------

# Server ka ABSOLUTE path — stdio client subprocess spawn karega, aur
# subprocess ka cwd kuch bhi ho sakta hai, isliye absolute path safest hai.
SERVER_PATH = str(Path(__file__).parent / "servers" / "greeter_server.py")


def groq_model(name: str = "llama-3.3-70b-versatile") -> OpenAIChatCompletionsModel:
    """Groq ka OpenAI-compatible endpoint -> Agents SDK ka model object."""
    client = AsyncOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
    )
    return OpenAIChatCompletionsModel(model=name, openai_client=client)


# Groq free tier ke rate limits PER-MODEL hote hain (tokens-per-day etc.) —
# agar ek model ka daily quota khatam ho jaaye to doosre model pe fallback
# kar sakte hain. Tool-calling support wale models hi list me rakhe hain.
GROQ_MODEL_CHAIN = [
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "llama-3.1-8b-instant",
]


# ===========================================================================
# PART A — DIRECT MCP CLIENT (no agent, no LLM)
#
# Yahan hum protocol ko RAW form me dekhte hain. Steps:
#   1. StdioServerParameters: batao kaunsi COMMAND se server spawn karna hai.
#   2. stdio_client(): subprocess spawn + stdin/stdout pipes ka pair deta hai.
#   3. ClientSession: in pipes ke upar JSON-RPC session.
#   4. session.initialize(): MCP HANDSHAKE — client/server capabilities
#      exchange hoti hain (jaise TCP ka hello).
#   5. list_tools() / call_tool() / read_resource(): actual kaam.
# ===========================================================================
async def part_a_direct_client() -> None:
    print("=" * 70)
    print("PART A — DIRECT MCP CLIENT (raw protocol, no LLM)")
    print("=" * 70)

    # Ye wahi command hai jo tum terminal me khud chala sakte the.
    # stdio_client ise SUBPROCESS ke roop me spawn karega.
    server_params = StdioServerParameters(command="uv", args=["run", SERVER_PATH])
    print(f"[spawn] subprocess: uv run {SERVER_PATH}")

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # MCP handshake — iske bina koi request allowed nahi.
            init_result = await session.initialize()
            print(f"[handshake] connected to server: '{init_result.serverInfo.name}' "
                  f"(protocol {init_result.protocolVersion})")

            # ---- TOOLS DISCOVERY: yahi MCP ka dil hai. Client ko pehle se
            # kuch nahi pata — server khud apne tools ka naam + description
            # + JSON schema bhejta hai.
            tools_result = await session.list_tools()
            print(f"\n[tools/list] server ne {len(tools_result.tools)} tools bataye:")
            for t in tools_result.tools:
                print(f"  - {t.name}: {t.description.splitlines()[0]}")
                print(f"      inputSchema properties: {list(t.inputSchema.get('properties', {}).keys())}")

            # ---- TOOL CALL #1 (no args)
            r1 = await session.call_tool("get_server_time", {})
            print(f"\n[tools/call] get_server_time() -> {r1.content[0].text}")

            # ---- TOOL CALL #2 (with args)
            r2 = await session.call_tool("greet_in_style", {"name": "Ashish", "style": "pirate"})
            print(f"[tools/call] greet_in_style(name='Ashish', style='pirate') -> {r2.content[0].text}")

            # ---- RESOURCE READ — note: ye tools/call nahi, resources/read hai.
            res = await session.read_resource("greeting://welcome")
            print(f"\n[resources/read] greeting://welcome ->\n  {res.contents[0].text}")

    # async with se bahar aate hi subprocess cleanly TERMINATE ho jaata hai.
    print("\n[cleanup] server subprocess band ho gaya (context manager exit).\n")


# ===========================================================================
# PART B — AGENTS SDK ROUTE (LLM decides tool calls)
#
# Ab framework ko kaam karne do. OpenAI Agents SDK me:
#   - MCPServerStdio = Part A ka saara boilerplate (spawn + handshake +
#     session) ek class me wrapped. Ye hamara MCP CLIENT hai.
#   - Agent(mcp_servers=[server]) — SDK har run se pehle server se
#     list_tools() karta hai aur saare MCP tools LLM ko function-calling
#     tools ki tarah de deta hai. LLM ko pata bhi nahi ki tool MCP se
#     aaya hai ya @function_tool se — same interface!
# ===========================================================================
async def part_b_agents_sdk() -> None:
    print("=" * 70)
    print("PART B — AGENTS SDK + MCP (Groq LLM khud tools chalayega)")
    print("=" * 70)

    params = {"command": "uv", "args": ["run", SERVER_PATH]}
    print(f"[spawn] MCPServerStdio subprocess: uv run {SERVER_PATH}")

    # client_session_timeout_seconds=60: `uv run` ko pehli baar env resolve
    # karne me time lag sakta hai, default 5s timeout chhota pad sakta hai.
    async with MCPServerStdio(params=params, client_session_timeout_seconds=60) as server:
        # Discovery yahan bhi dikhate hain — SDK ke through:
        tools = await server.list_tools()
        print(f"[discovery] SDK ko {len(tools)} MCP tools mile: {[t.name for t in tools]}")

        task = (
            "Step 1: call get_server_time and report the exact time it returns. "
            "Step 2: call greet_in_style with name='Ashish' and style='hinglish' "
            "and report the exact greeting. Give both results clearly."
        )
        print(f"\n[task] {task}\n")

        instructions = (
            "You are a helpful assistant. Use the available tools: "
            "get_server_time for the current time, greet_in_style for "
            "greetings. IMPORTANT: copy tool results VERBATIM into your "
            "final answer — never invent or alter dates, times or greetings."
        )

        # Groq free tier: transient 429/503 + per-model daily token limits.
        # Strategy: har model pe 2 attempts, fail ho to chain ke agle model
        # pe fallback. NOTE: MCP server WAHI rehta hai — sirf LLM badla.
        # Yahi to MCP ka point hai: tools LLM se decoupled hain!
        last_err: Exception | None = None
        done = False
        for model_name in GROQ_MODEL_CHAIN:
            agent = Agent(
                name="GreeterAgent",
                instructions=instructions,
                model=groq_model(model_name),
                mcp_servers=[server],  # <- bas itna! SDK baaki sab handle karega.
            )
            for attempt in range(1, 3):
                try:
                    result = await Runner.run(agent, task)
                    print(f"[agent final output — model={model_name}]\n{result.final_output}")
                    done = True
                    break
                except Exception as e:
                    last_err = e
                    print(f"[retry] model={model_name} attempt {attempt} fail: "
                          f"{str(e)[:160]}")
                    await asyncio.sleep(3)
            if done:
                break
        if not done:
            print(f"[fail] saare models/attempts fail ho gaye: {last_err}")

    print("\n[cleanup] MCPServerStdio context exit — subprocess terminated.")


async def main() -> None:
    await part_a_direct_client()
    await part_b_agents_sdk()
    print("\n" + "=" * 70)
    print("LAB 1 DONE — Direct client (raw protocol) + Agents SDK (LLM-driven),")
    print("dono routes se EK HI MCP server use hua. Yahi MCP ki portability hai.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
