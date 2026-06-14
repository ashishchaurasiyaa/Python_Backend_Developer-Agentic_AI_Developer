"""
LAB 1 — AutoGen AgentChat Basics: AssistantAgent + Tools + Database (Lectures L91-L94)
=======================================================================================

KYA SEEKHENGE:
    1. AutoGen ka 3-layer architecture (core / agentchat / ext) — kaunsi layer kab use hoti hai
    2. Pehla AssistantAgent banana aur `agent.run(task=...)` se single-shot jawab lena
    3. Tools as plain Python functions + SQLite database lookup (L93 ka airline pattern)
       — aur PROOF ke tool genuinely call hua (ToolCallRequestEvent/ToolCallExecutionEvent)
    4. Multi-turn conversation `on_messages()` se — agent object apni chat history yaad rakhta hai

KAISE CHALANA:
    cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
    uv run Udemy_EdDonner_Course/Week5_AutoGen/Practical/lab1_agentchat_basics.py

AUTOGEN = TEEN LAYERS (yeh mental model poore week kaam aayega):
    - autogen-core      → low-level: message-passing runtime, RoutedAgent, event-driven
                          actors. Distributed/advanced systems ke liye. (Lab 3-4 me)
    - autogen-agentchat → HIGH-LEVEL: ready-made agents (AssistantAgent), Teams
                          (RoundRobinGroupChat), termination conditions. HAMARA MAIN FOCUS.
                          Core ke upar bana hua hai — jaise requests urllib ke upar.
    - autogen-ext       → integrations: model clients (OpenAIChatCompletionClient),
                          code executors, vector DBs etc. Provider-specific cheezein yahan.

    Microsoft ka framework hai. 0.4 me COMPLETE REWRITE hua (purana 0.2 API bilkul alag
    tha — pyautogen). Course AutoGen 0.5.1 use karta hai, hum 0.7.5 par hain — same API
    family (agentchat/core/ext split), is lab ke liye koi breaking difference nahi.

VERSION NOTE: 0.7.5 me bhi AssistantAgent / run / on_messages ka signature 0.5.x jaisa hi
hai. Model: free Groq (llama-3.3-70b) via OpenAI-compatible endpoint — OPENAI_API_KEY
ki zaroorat nahi.
"""

import asyncio
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

# ---- AgentChat layer (high-level) ----
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import (
    TextMessage,
    ToolCallRequestEvent,
    ToolCallExecutionEvent,
)

# ---- Core layer (sirf CancellationToken yahan se — baaki core Lab 3 me) ----
from autogen_core import CancellationToken
from autogen_core.models import ModelInfo

# ---- Ext layer (model client = provider integration) ----
from autogen_ext.models.openai import OpenAIChatCompletionClient

load_dotenv(override=True)

# =========================================================================
# MODEL CLIENT — autogen-ext ka OpenAIChatCompletionClient kisi bhi
# OpenAI-compatible endpoint par point ho sakta hai. Groq free hai aur
# /openai/v1 route deta hai, bas model_info HUME batana padta hai kyunki
# client llama models ko apne capability-table me nahi pehchanta.
# =========================================================================
def groq_client(model: str = "llama-3.3-70b-versatile") -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(
        model=model,
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
        model_info=ModelInfo(
            vision=False,
            function_calling=True,   # tools ke liye zaroori — Groq llama-3.3 supports it
            json_output=True,
            family="llama-3.3-70b",
            structured_output=True,
        ),
    )


# Free Groq tier par kabhi-kabhi transient 429/503 aate hain, aur llama kabhi
# malformed tool-call syntax bhi nikal deta hai (400 tool_use_failed) — dono
# retry se theek ho jaate hain. Isliye chhota retry wrapper.
async def with_retry(coro_factory, attempts: int = 3, delay: float = 5.0):
    for i in range(1, attempts + 1):
        try:
            return await coro_factory()
        except Exception as e:
            if i == attempts:
                raise
            print(f"    [retry] attempt {i} failed ({type(e).__name__}: {e}) — {delay}s wait...")
            await asyncio.sleep(delay)


# =========================================================================
# PART 3 PREP — SQLite DATABASE (L93 ka pattern)
# Ed ke lab me airline ticket prices ek DB me hain aur agent TOOL ke through
# unhe padhta hai — LLM ke paas prices nahi hain, woh sirf function call
# karna jaanta hai. Yehi "grounding via tools" ka core idea hai.
# =========================================================================
OUTPUT_DIR = Path(__file__).parent / "output"
DB_PATH = OUTPUT_DIR / "tickets.db"


def setup_database() -> None:
    """Chhota tickets.db banao aur seed karo (idempotent — har run par fresh seed)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DROP TABLE IF EXISTS prices")
        conn.execute("CREATE TABLE prices (city TEXT PRIMARY KEY, price_usd REAL)")
        conn.executemany(
            "INSERT INTO prices (city, price_usd) VALUES (?, ?)",
            [("paris", 499.0), ("london", 449.0), ("tokyo", 899.0), ("berlin", 399.0)],
        )
        conn.commit()
    finally:
        conn.close()


# =========================================================================
# TOOLS — AgentChat me tool = plain Python function (sync ya async) jisme
# type hints + docstring ho. tools=[fn] dene par AgentChat khud FunctionTool
# wrap kar leta hai; docstring hi LLM ke liye tool-description ban jaati hai,
# isliye usse dhang se likho. (OpenAI SDK me jo JSON schema haath se likhte
# the, woh yahan free me mil jaata hai.)
# =========================================================================
def get_ticket_price(city: str) -> str:
    """Get the round-trip ticket price in USD for a destination city."""
    print(f"    [TOOL CALLED] get_ticket_price(city={city!r})")  # proof ke function chala
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT price_usd FROM prices WHERE city = ?", (city.strip().lower(),)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return f"Sorry, we don't fly to {city}."
    return f"A round-trip ticket to {city.title()} costs ${row[0]:.2f}."


def list_cities() -> str:
    """List all destination cities this airline serves."""
    print("    [TOOL CALLED] list_cities()")
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("SELECT city FROM prices ORDER BY city").fetchall()
    finally:
        conn.close()
    return "We serve: " + ", ".join(r[0].title() for r in rows)


# =========================================================================
# DEMO 1 — FIRST AGENT (L91-L92): bina tools ke ek simple AssistantAgent.
# `agent.run(task=...)` = sabse easy entrypoint: TaskResult deta hai jisme
# .messages = poora exchange (user task + agent reply).
# =========================================================================
async def demo_first_agent() -> None:
    print("=" * 70)
    print("DEMO 1: First AssistantAgent — simple run(task=...)")
    print("=" * 70)

    client = groq_client()
    agent = AssistantAgent(
        name="flight_assistant",
        model_client=client,
        # system_message = agent ka persona. AgentChat isse model context me
        # SystemMessage ke roop me daal deta hai.
        system_message=(
            "You are a friendly assistant for SkyHigh Airlines. "
            "You are cheerful, concise, and you love adding a touch of humor."
        ),
    )

    result = await with_retry(
        lambda: agent.run(task="Say a one-line cheerful welcome to a nervous first-time flyer.")
    )

    # result.messages me TextMessage objects hain — source batata hai kisne bheja.
    for msg in result.messages:
        print(f"  [{msg.source}] {msg.content}")
    await client.close()  # 0.7.x me client explicitly close karna clean practice hai
    print()


# =========================================================================
# DEMO 2 — TOOLS + DATABASE (L93): agent ko functions de do, woh khud decide
# karta hai kab call karna hai. reflect_on_tool_use=True ka matlab: tool ka
# raw output user ko directly nahi jaata — LLM ek aur pass karke usse
# natural-language jawab me convert karta hai.
# =========================================================================
async def demo_tools_with_db() -> None:
    print("=" * 70)
    print("DEMO 2: Tools + SQLite — agent DB se prices nikalta hai")
    print("=" * 70)

    client = groq_client()
    agent = AssistantAgent(
        name="ticket_agent",
        model_client=client,
        system_message=(
            "You are a helpful SkyHigh Airlines booking assistant. "
            "ALWAYS use your tools to answer questions about prices and destinations — "
            "never guess prices."
        ),
        tools=[get_ticket_price, list_cities],  # plain functions — auto FunctionTool
        reflect_on_tool_use=True,  # tool result ke baad LLM summary/natural answer
    )

    result = await with_retry(
        lambda: agent.run(
            task="How much is a ticket to Paris and which cities do you serve?"
        )
    )

    # PROOF: messages stream me tool events explicit dikhte hain —
    #   ToolCallRequestEvent  = LLM ne function-call maanga (name + arguments)
    #   ToolCallExecutionEvent = AgentChat ne function chala ke result capture kiya
    # Yeh transparency 0.4+ rewrite ka bada win hai (purane 0.2 me yeh sab opaque tha).
    tool_event_seen = False
    for msg in result.messages:
        kind = type(msg).__name__
        if isinstance(msg, ToolCallRequestEvent):
            tool_event_seen = True
            calls = ", ".join(f"{c.name}({c.arguments})" for c in msg.content)
            print(f"  [{kind}] {calls}")
        elif isinstance(msg, ToolCallExecutionEvent):
            results = " | ".join(str(r.content) for r in msg.content)
            print(f"  [{kind}] {results}")
        else:
            print(f"  [{kind} from {msg.source}] {msg.content}")

    print(f"\n  >> Tool genuinely call hua? {'YES' if tool_event_seen else 'NO (problem!)'}")
    await client.close()
    print()


# =========================================================================
# DEMO 3 — MULTI-TURN (L94): on_messages() lower-level entrypoint hai —
# tum TextMessage list bhejte ho, Response milta hai (.chat_message = final
# jawab, .inner_messages = beech ke tool events).
#
# IMPORTANT CONCEPT: AssistantAgent STATEFUL hai — har on_messages() call
# uski internal model_context me append hota hai. Isliye turn 2 me agent ko
# turn 1 yaad rahta hai, WITHOUT humein history dobara bhejne ki zaroorat.
# (State sirf isi Python object me hai — naya agent banaoge to bhool jaayega;
# persist karne ke liye save_state()/load_state() hota hai, woh aage dekhenge.)
# =========================================================================
async def demo_multi_turn() -> None:
    print("=" * 70)
    print("DEMO 3: Multi-turn — on_messages(), agent state yaad rakhta hai")
    print("=" * 70)

    client = groq_client()
    agent = AssistantAgent(
        name="memory_agent",
        model_client=client,
        system_message=(
            "You are a SkyHigh Airlines assistant. Use tools for prices. Be concise."
        ),
        tools=[get_ticket_price],
        reflect_on_tool_use=True,
    )

    # ---- TURN 1: user apna naam + sawal bhejta hai ----
    print("  [user] My name is Ashish. How much is a ticket to Tokyo?")
    resp1 = await with_retry(
        lambda: agent.on_messages(
            [TextMessage(content="My name is Ashish. How much is a ticket to Tokyo?",
                         source="user")],
            CancellationToken(),  # core layer ka token — long ops cancel karne ke liye
        )
    )
    print(f"  [{agent.name}] {resp1.chat_message.content}")

    # ---- TURN 2: naam dobara NAHI bataya — agent ko context se yaad hona chahiye ----
    print("\n  [user] What is my name, and is Berlin cheaper than that city?")
    resp2 = await with_retry(
        lambda: agent.on_messages(
            [TextMessage(content="What is my name, and is Berlin cheaper than that city?",
                         source="user")],
            CancellationToken(),
        )
    )
    print(f"  [{agent.name}] {resp2.chat_message.content}")

    await client.close()
    print()


async def main() -> None:
    setup_database()
    print(f"Database seeded at: {DB_PATH}\n")
    try:
        await demo_first_agent()
        await demo_tools_with_db()
        await demo_multi_turn()
        print("Lab 1 complete — AgentChat basics done. Next: teams (RoundRobinGroupChat).")
    except Exception as e:
        # Graceful failure — free-tier APIs kabhi down ho sakte hain.
        print(f"\nLab failed after retries: {type(e).__name__}: {e}")
        print("Tip: GROQ_API_KEY check karo ya thodi der baad dobara chalao.")


if __name__ == "__main__":
    asyncio.run(main())
