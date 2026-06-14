"""
LAB 1 — OpenAI Agents SDK Fundamentals + Async (Lectures L28-L32)
==================================================================

Is lab me kya seekhenge:
  1. ASYNC PRIMER (L28)      — Agents SDK async-first kyun hai? Sequential vs
                               concurrent (asyncio.gather) timing compare karke
                               khud dekhenge.
  2. FIRST AGENT (L29-L30)   — Agent(name, instructions, model) banana aur
                               Runner.run() se chalana. Bas 3 lines me agent!
  3. AGENT + TOOL (L31-L32)  — @function_tool decorator se Python function ko
                               tool banana. SDK khud tool-call loop handle
                               karta hai (Week 1 lab5 me jo manual while-loop
                               likha tha, wo ab SDK ke andar built-in hai).
  4. TRACING NOTE            — OpenAI platform tracing kya hai aur yahan
                               disabled kyun hai (comment block dekho).

Kaise chalana hai:
  cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
  uv run Udemy_EdDonner_Course/Week2_OpenAI_Agents_SDK/Practical/lab1_agents_sdk_basics.py

LLM: Groq (free) — llama-3.3-70b-versatile via OpenAI-compatible endpoint.
"""

import os
import time
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import (
    Agent,
    Runner,
    OpenAIChatCompletionsModel,
    function_tool,
    set_tracing_disabled,
)

load_dotenv(override=True)

# ---------------------------------------------------------------------------
# TRACING NOTE (L32 — Trace / Observability):
#
# OpenAI Agents SDK by-default har Runner.run() ka ek "trace" banata hai —
# agent ke saare LLM calls, tool calls, handoffs ka timeline — aur use
# platform.openai.com/traces pe upload karta hai. Ye debugging ke liye
# zabardast hai: production me dikh jaata hai ki agent ne kaunsa tool kab
# call kiya, kitna time laga, kya input/output tha.
#
# LEKIN upload ke liye VALID OpenAI API key chahiye. Hamare .env me
# OPENAI_API_KEY invalid hai (hum free Groq use kar rahe hain), isliye
# tracing OFF kar rahe hain — warna har run pe background me 401 errors
# ki spam aati.
#
# Production me (valid key ke saath) aise enable karte:
#     from agents import set_tracing_export_api_key
#     set_tracing_export_api_key(os.getenv("OPENAI_API_KEY"))
# Note: tracing key alag ho sakti hai LLM key se — yani LLM Groq pe chala lo,
# par traces OpenAI platform pe bhejo. Best of both worlds.
# ---------------------------------------------------------------------------
set_tracing_disabled(True)

GROQ_MODEL = "llama-3.3-70b-versatile"  # free + tool-calling supported


def groq_model(model_name: str = GROQ_MODEL) -> OpenAIChatCompletionsModel:
    """
    Groq ko OpenAI Agents SDK me plug karne ka adapter.

    SDK by-default OpenAI ke models expect karta hai, lekin
    OpenAIChatCompletionsModel + custom AsyncOpenAI client se KOI BHI
    OpenAI-compatible endpoint (Groq, Gemini, Ollama...) use kar sakte ho.
    Ed Donner course me bhi yahi trick sikhayi jaati hai paisa bachane ke liye.
    """
    client = AsyncOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
    )
    return OpenAIChatCompletionsModel(model=model_name, openai_client=client)


# ===========================================================================
# STEP 1 — ASYNC PRIMER (L28): SDK async-first kyun hai?
# ===========================================================================
# Agent ka 90% time NETWORK WAIT me jaata hai (LLM API response ka intezaar).
# Sync code me CPU bas baitha rehta hai. Async me ek await ke dauraan event
# loop doosra kaam utha leta hai — isliye multi-agent systems (parallel
# agents, parallel tool calls) async ke bina practically impossible hain.
# Runner.run() bhi isi wajah se coroutine hai — use 'await' karna padta hai.


async def fake_llm_call(name: str, seconds: float) -> str:
    """
    Nakli LLM call — asyncio.sleep network wait simulate karta hai.
    Real LLM call me bhi exactly yahi hota: 'await' pe ruk ke event loop
    free ho jaata hai, doosre coroutines chal sakte hain.
    """
    await asyncio.sleep(seconds)
    return f"{name} done in ~{seconds}s"


async def step1_async_primer() -> None:
    print("=" * 70)
    print("STEP 1 — ASYNC PRIMER: sequential vs concurrent (L28)")
    print("=" * 70)

    # --- Sequential: ek ke baad ek await => time ADD hota hai (1s + 1s = 2s)
    t0 = time.perf_counter()
    r1 = await fake_llm_call("call-A", 1.0)
    r2 = await fake_llm_call("call-B", 1.0)
    seq_time = time.perf_counter() - t0
    print(f"  Sequential : {r1} | {r2}")
    print(f"  Sequential total = {seq_time:.2f}s  (1s + 1s, ek ke baad ek)")

    # --- Concurrent: asyncio.gather dono ko EK SAATH start karta hai =>
    #     total time = max(1s, 1s) = ~1s. Yahi superpower hai multi-agent me:
    #     5 agents ko parallel bhejo, time 5x nahi, ~1x hi lagta hai.
    t0 = time.perf_counter()
    r1, r2 = await asyncio.gather(
        fake_llm_call("call-A", 1.0),
        fake_llm_call("call-B", 1.0),
    )
    con_time = time.perf_counter() - t0
    print(f"  Concurrent : {r1} | {r2}")
    print(f"  Concurrent total = {con_time:.2f}s  (gather => dono ek saath)")
    print(
        f"  >>> Speedup ~{seq_time / con_time:.1f}x — isliye Agents SDK "
        f"async-first hai!\n"
    )


# ===========================================================================
# STEP 2 — FIRST AGENT (L29-L30): Agent + Runner.run()
# ===========================================================================
# Agents SDK ke 3 core concepts:
#   Agent  = LLM + instructions (system prompt) + (optional) tools/handoffs
#   Runner = agent ko chalane wala engine (LLM calls + tool loop sab handle)
#   result.final_output = agent ka aakhri jawab (string ya Pydantic object)


async def step2_first_agent() -> None:
    print("=" * 70)
    print("STEP 2 — FIRST AGENT: jokes about AI engineers (L29-L30)")
    print("=" * 70)

    # Bas itna hi! Koi manual messages list nahi, koi while-loop nahi.
    joker = Agent(
        name="Jokester",
        instructions=(
            "You are a comedian who tells short, witty jokes about "
            "AI engineers. Keep it to 2-3 lines."
        ),
        model=groq_model(),  # default OpenAI ki jagah free Groq
    )

    # Runner.run() coroutine hai => await zaroori. Ye internally:
    # input -> LLM call -> (tool calls if any) -> final output, sab karta hai.
    result = await Runner.run(joker, "Tell me a joke about AI engineers.")

    print(f"  Agent ka jawab:\n  {result.final_output}\n")


# ===========================================================================
# STEP 3 — AGENT + TOOL (L31-L32): @function_tool magic
# ===========================================================================
# Week 1 lab5 me humne MANUALLY kiya tha:
#   while True:
#       response = llm.chat(...)
#       if response.tool_calls:
#           result = call_python_function(...)   # khud dispatch
#           messages.append(tool_result)         # khud history manage
#       else: break
#
# Agents SDK me ye POORA loop built-in hai. Hum bas:
#   1. Python function pe @function_tool laga do
#      (docstring + type hints se SDK khud JSON schema bana leta hai!)
#   2. Agent(tools=[...]) me pass kar do
# Baaki sab — schema banana, tool-call detect karna, function execute karna,
# result wapas LLM ko bhejna — SDK handle karta hai.


# GROQ QUIRK (mila run karte waqt): zero-argument tool (def f() -> str) ka
# empty schema Groq 400 error deta hai — "'required' present but 'properties'
# is missing". Fix: tool ko kam-se-kam EK parameter do. Isliye get_current_time
# me 'timezone' param add kiya — waise bhi zyada useful tool ban gaya!
@function_tool
def get_current_time(timezone: str) -> str:
    """Returns the current date and time for the given IANA timezone
    (e.g. 'Asia/Kolkata', 'America/New_York'). Use 'local' if unknown."""
    # LLM ko time nahi pata (training cutoff!) — ye tool use ground truth deta
    # hai. SDK is function ka naam + docstring + type hints se khud JSON
    # schema banakar LLM ko bhejta hai.
    try:
        tz = None if timezone == "local" else ZoneInfo(timezone)
    except Exception:
        tz = None  # galat timezone naam aaye to local time, crash nahi
    return datetime.now(tz).strftime("%A, %d %B %Y, %I:%M %p")


@function_tool
def word_count(text: str) -> int:
    """Counts the number of words in the given text."""
    # LLMs counting me weak hain (tokens dekhte hain, words nahi) —
    # deterministic Python tool 100% sahi jawab dega.
    return len(text.split())


async def step3_agent_with_tools() -> None:
    print("=" * 70)
    print("STEP 3 — AGENT + TOOLS: SDK ka built-in tool loop (L31-L32)")
    print("=" * 70)

    assistant = Agent(
        name="ToolUser",
        instructions=(
            "You are a precise assistant. Use the provided tools to answer "
            "questions about time or word counts. Never guess — always call "
            "the tool."
        ),
        model=groq_model(),
        tools=[get_current_time, word_count],  # bas list me daal do, done!
    )

    # Query aisi jo DONO tools trigger kare — SDK multiple tool-call rounds
    # bhi khud handle karega (LLM -> tool -> LLM -> tool -> final answer).
    query = (
        "What is the current time? Also, how many words are in this "
        "sentence: 'Agents SDK handles the tool loop for us'?"
    )
    print(f"  User query: {query}")

    result = await Runner.run(assistant, query)
    print(f"\n  Agent ka final jawab:\n  {result.final_output}")

    # Proof ke liye: result.new_items me poori journey hoti hai —
    # kaunse tool calls hue, kya outputs aaye. (Trace ka local version samjho.)
    tool_calls = [
        item for item in result.new_items if item.type == "tool_call_item"
    ]
    print(
        f"\n  Behind the scenes: SDK ne {len(tool_calls)} tool call(s) "
        f"automatically execute kiye — humne koi while-loop nahi likha!\n"
    )


# ===========================================================================
# MAIN — saare steps ek hi event loop me, ek hi asyncio.run() se
# ===========================================================================
async def main() -> None:
    if not os.getenv("GROQ_API_KEY"):
        # Defensive: bina key ke crash nahi, saaf message do.
        print("ERROR: GROQ_API_KEY .env me nahi mili. Step 1 (async primer)")
        print("phir bhi chalega, lekin agent steps skip ho jayenge.")
        await step1_async_primer()
        return

    await step1_async_primer()       # no LLM needed — pure asyncio demo

    # Free Groq tier kabhi-kabhi transient error de deta hai (rate limit /
    # momentary 5xx). Isliye LLM-wale steps ko ek simple retry me wrap karte
    # hain — production agents me bhi yahi pattern hota hai (retry + backoff).
    for step in (step2_first_agent, step3_agent_with_tools):
        for attempt in (1, 2, 3):
            try:
                await step()
                break
            except Exception as e:
                if attempt == 3:
                    raise
                print(f"  [retry] {step.__name__} fail hua ({type(e).__name__}) — "
                      f"{attempt}/2 retry, 3s wait...")
                await asyncio.sleep(3)

    print("=" * 70)
    print("LAB 1 COMPLETE — Agent banana, chalana, aur tools dena aa gaya!")
    print("Next: handoffs + multi-agent patterns (Lab 2)")
    print("=" * 70)


if __name__ == "__main__":
    # Ek hi asyncio.run() — saara async code ek event loop me chalta hai.
    asyncio.run(main())
