"""
LAB 2 — Sales Agents: Parallel Agents, Agents-as-Tools, Handoffs (L33-L38)
===========================================================================

Ed Donner ke SDR (Sales Development Rep) project ka recreation — OpenAI Agents SDK pe,
lekin FREE Groq backend ke saath.

Is lab me kya seekhenge:
  PART 1+2 (L33-L34): Teen alag PERSONA wale email-writer agents banana, aur unhe
                      asyncio.gather se PARALLEL chalana (3 LLM calls ek saath!).
  PART 3   (L35):     AGENTS-AS-TOOLS — ek agent ko .as_tool() se kisi DUSRE agent
                      ka tool bana dena. "Sales Manager" teeno writers ko tools ki
                      tarah call karke BEST email choose karta hai.
  PART 4   (L36-L38): HANDOFF — manager kaam poora karke conversation hi
                      "Email Formatter" agent ko TRANSFER kar deta hai, jo subject
                      line + HTML formatting karke send_email tool se bhejta hai.
                      (Course me SendGrid se REAL email jaati hai — humne free
                      file-based mock banaya hai jo outbox.txt me append karta hai.)

Kaise chalana hai:
  cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
  uv run Udemy_EdDonner_Course/Week2_OpenAI_Agents_SDK/Practical/lab2_sales_agents_handoffs.py

===========================================================================
AGENTS-AS-TOOLS vs HANDOFF — sabse important conceptual difference is lab ka:
===========================================================================

  AGENT-AS-TOOL (.as_tool()):
    - Manager writer ko "function call" ki tarah use karta hai.
    - Writer apna jawab deta hai, aur CONTROL WAPAS manager ke paas aa jaata hai.
    - Manager hi conversation ka owner rehta hai — wo 3 tools call kar sakta hai,
      results compare kar sakta hai, aur khud final jawab de sakta hai.
    - Socho: boss ne intern se draft mangwaya, intern ne draft diya, boss aage
      ka decision khud lega. (Sub-routine call jaisa.)

  HANDOFF (handoffs=[...]):
    - Manager poori CONVERSATION hi doosre agent ko TRANSFER kar deta hai.
    - Control WAPAS NAHI aata — ab Email Formatter hi "current agent" hai,
      wohi final_output dega, wohi tools call karega.
    - SDK internally handoff ko bhi ek special tool ki tarah expose karta hai
      ("transfer_to_<agent>"), lekin semantics alag hai: baton-pass, return nahi.
    - Socho: receptionist ne call billing department ko TRANSFER kar di —
      ab billing hi customer se baat karega, receptionist picture se bahar.

  Rule of thumb:
    - Result chahiye aur aage khud decide karna hai  -> AGENT-AS-TOOL
    - Responsibility hi shift karni hai (specialist
      ko aage ka pura kaam dena hai)                 -> HANDOFF
===========================================================================
"""

import os
import asyncio
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel
from agents import (
    Agent,
    Runner,
    OpenAIChatCompletionsModel,
    RunContextWrapper,
    function_tool,
    handoff,
    set_tracing_disabled,
)

load_dotenv(override=True)
# Tracing OpenAI platform pe jaata hai; hamare paas valid OPENAI_API_KEY nahi — isliye OFF.
set_tracing_disabled(True)

# ---------------------------------------------------------------------------
# Groq model helper — OpenAI Agents SDK ko Groq ke OpenAI-compatible endpoint
# pe point karte hain. llama-3.3-70b tool-calling support karta hai, aur free hai.
# ---------------------------------------------------------------------------
GROQ_MODEL = "llama-3.3-70b-versatile"


def groq_model(model_name: str = GROQ_MODEL) -> OpenAIChatCompletionsModel:
    client = AsyncOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
    )
    return OpenAIChatCompletionsModel(model=model_name, openai_client=client)


# ---------------------------------------------------------------------------
# Mock "send_email" tool — course me Ed SendGrid API use karta hai (sendgrid lib,
# SENDGRID_API_KEY, real email send hoti hai). Hum free rahenge: email ko ek
# local outbox.txt file me APPEND karte hain. Concept bilkul same — agent ek
# @function_tool call karta hai jo side-effect (email send) perform karta hai.
# ---------------------------------------------------------------------------
OUTBOX_PATH = Path(__file__).resolve().parent / "outbox.txt"


@function_tool
def send_email(subject: str, html_body: str) -> str:
    """Send a sales email with the given subject and HTML body.

    Args:
        subject: The email subject line.
        html_body: The full email body, formatted in simple HTML.
    """
    # Defensive: file write fail ho to agent ko readable error string milti hai,
    # crash nahi hota — LLM error dekh ke gracefully respond kar sakta hai.
    try:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = (
            f"\n{'=' * 70}\n"
            f"SENT AT : {stamp}\n"
            f"SUBJECT : {subject}\n"
            f"{'-' * 70}\n"
            f"{html_body}\n"
            f"{'=' * 70}\n"
        )
        with open(OUTBOX_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
        print(f"   [send_email tool] -> outbox.txt me append hua (subject: {subject!r})")
        return f"Email sent successfully (appended to outbox.txt) with subject: {subject}"
    except Exception as e:
        return f"Failed to send email: {e}"


# ---------------------------------------------------------------------------
# PART 1 — Teen sales-email writers, alag-alag PERSONA (L33)
# Same task, alag instructions => alag style ke drafts. Yahi "persona pattern" hai:
# ek hi underlying model, sirf system prompt badal ke teen "alag employees" mil gaye.
# ---------------------------------------------------------------------------
COMPANY_PITCH = (
    "You work for AgentForge AI, a consultancy that builds production-grade "
    "AI agent systems (RAG pipelines, multi-agent workflows, LLM integrations) "
    "for mid-size companies."
)

professional_writer = Agent(
    name="Professional Sales Writer",
    instructions=(
        f"{COMPANY_PITCH} You write serious, professional cold sales emails. "
        "Formal tone, credibility-focused, clear value proposition. "
        "Keep the email under 120 words. Output ONLY the email body, no preamble."
    ),
    model=groq_model(),
)

witty_writer = Agent(
    name="Witty Sales Writer",
    instructions=(
        f"{COMPANY_PITCH} You write humorous, engaging cold sales emails that are "
        "likely to get a response because they make the reader smile. Light jokes, "
        "playful tone, but still a clear ask. Keep the email under 120 words. "
        "Output ONLY the email body, no preamble."
    ),
    model=groq_model(),
)

concise_writer = Agent(
    name="Concise Sales Writer",
    instructions=(
        f"{COMPANY_PITCH} You write extremely short, busy-executive-friendly cold "
        "sales emails. Maximum 50 words. No fluff, straight to the point, one clear "
        "call to action. Output ONLY the email body, no preamble."
    ),
    model=groq_model(),
)

SALES_TASK = (
    "Write a cold sales email to a CTO pitching our AI consulting service "
    "(building custom AI agents for their business)."
)


# ---------------------------------------------------------------------------
# PART 2 — PARALLEL execution with asyncio.gather (L34)
# Teen independent LLM calls hain — inka aapas me koi dependency nahi, to inhe
# sequentially chalana time-waste hai. asyncio.gather teeno coroutines ko ek
# saath schedule karta hai => total time ~= slowest call (3x speedup, roughly).
# Yahi "parallel agents" pattern hai — agentic workflows me bohot common.
# ---------------------------------------------------------------------------
async def part2_parallel_drafts() -> None:
    print("\n" + "#" * 70)
    print("# PART 2 (L34): PARALLEL — teen writers, asyncio.gather, ek saath")
    print("#" * 70)

    results = await asyncio.gather(
        Runner.run(professional_writer, SALES_TASK),
        Runner.run(witty_writer, SALES_TASK),
        Runner.run(concise_writer, SALES_TASK),
    )

    for result in results:
        print(f"\n--- Draft from: {result.last_agent.name} ---")
        print(result.final_output)


# ---------------------------------------------------------------------------
# PART 3 — AGENTS AS TOOLS (L35)
# .as_tool() ek agent ko callable tool me convert kar deta hai. Manager LLM ko
# bas teen "functions" dikhte hain — wo unhe call karta hai, har call ke andar
# SDK us writer-agent ka pura run karta hai, aur final_output tool-result ban ke
# manager ke paas WAPAS aata hai. Control manager ke paas hi rehta hai.
# ---------------------------------------------------------------------------
writer_tools = [
    professional_writer.as_tool(
        tool_name="professional_email_writer",
        tool_description="Writes a serious, professional cold sales email for the given brief.",
    ),
    witty_writer.as_tool(
        tool_name="witty_email_writer",
        tool_description="Writes a humorous, engaging cold sales email for the given brief.",
    ),
    concise_writer.as_tool(
        tool_name="concise_email_writer",
        tool_description="Writes an extremely short, to-the-point cold sales email for the given brief.",
    ),
]

sales_manager_pick_best = Agent(
    name="Sales Manager",
    instructions=(
        "You are a sales manager. You NEVER write emails yourself. "
        "Use ALL THREE writer tools exactly once each with the user's brief, "
        "compare the three drafts, and then reply with the single best email "
        "(copy it verbatim) plus ONE short line explaining why you picked it."
    ),
    tools=writer_tools,
    model=groq_model(),
)


async def part3_agents_as_tools() -> None:
    print("\n" + "#" * 70)
    print("# PART 3 (L35): AGENTS-AS-TOOLS — manager teeno writers ko tool ki")
    print("# tarah call karta hai, control wapas manager ke paas aata hai")
    print("#" * 70)

    result = await Runner.run(sales_manager_pick_best, SALES_TASK, max_turns=15)
    print(f"\n--- Manager ka final verdict (last_agent: {result.last_agent.name}) ---")
    print(result.final_output)


# ---------------------------------------------------------------------------
# PART 4 — HANDOFF (L36-L38)
# Email Formatter ek SPECIALIST agent hai: subject line likhta hai, body ko
# simple HTML me convert karta hai, aur phir send_email tool call karta hai.
# Manager ke paas handoffs=[email_formatter] hai — jab manager best email choose
# kar leta hai, wo conversation ko formatter ko HAND OFF kar deta hai.
# Iske baad control manager ke paas WAPAS NAHI aata — formatter hi run khatam
# karta hai (notice karna: result.last_agent ab "Email Formatter" hoga!).
# ---------------------------------------------------------------------------
email_formatter = Agent(
    name="Email Formatter",
    instructions=(
        "You receive a chosen sales email from a sales manager. Your job: "
        "1) Write a compelling subject line for it. "
        "2) Convert the email body to simple HTML (<p> paragraphs, <strong> for "
        "emphasis, a signature block). "
        "3) Call the send_email tool with that subject and HTML body. "
        "4) After the tool confirms, reply with a one-line confirmation that the "
        "email was sent, including the subject line you used."
    ),
    tools=[send_email],
    # Handoff description: handing-off agent ke LLM ko yeh text dikhta hai —
    # isi se wo decide karta hai ki transfer kab/kisko karna hai.
    handoff_description="Formats a finished sales email (subject + HTML) and sends it.",
    model=groq_model(),
)

# --- Custom handoff object (handoff() helper) ---
# Do wajah se simple handoffs=[email_formatter] ki jagah handoff(...) use kiya:
#   1) GROQ QUIRK: SDK ka default handoff-tool EMPTY parameter schema bhejta hai
#      ('required' hai par 'properties' nahi) — Groq strict validation isse
#      400 error ke saath REJECT kar deta hai. input_type dene se schema me
#      real properties aa jaati hain => Groq khush.
#   2) BONUS LEARNING: structured HANDOFF INPUT — manager ko explicitly winning
#      email pass karni padti hai (Ed bhi course me handoff inputs dikhata hai).
#   3) Agent name me space hai ("Email Formatter") => default tool name invalid
#      ban raha tha; tool_name_override se clean naam diya.
class WinningEmail(BaseModel):
    winning_email: str  # manager jo best draft choose karega, wo yahan aayega


# Contract: yeh ek SYNC callback hai jise Agents SDK handoff hote waqt
# (ctx, input) ke saath call karta hai. 'input' parsed WinningEmail object hai
# kyunki niche handoff() ko input_type=WinningEmail diya gaya hai.
def on_email_handoff(ctx: RunContextWrapper, input: WinningEmail) -> None:
    # Handoff hone ke moment pe yeh callback fire hota hai — debugging/logging
    # ke liye perfect jagah (e.g. analytics event, audit log).
    print(f"   [HANDOFF fired] Manager -> Email Formatter "
          f"(winning email: {len(input.winning_email)} chars)")


email_formatter_handoff = handoff(
    agent=email_formatter,
    tool_name_override="transfer_to_email_formatter",
    tool_description_override=(
        "Transfer the conversation to the Email Formatter, passing the full text "
        "of the winning sales email so it can be formatted and sent."
    ),
    input_type=WinningEmail,
    on_handoff=on_email_handoff,
)

sales_manager_with_handoff = Agent(
    name="Sales Manager (with handoff)",
    instructions=(
        "You are a sales manager. You NEVER write, format, or send emails yourself. "
        "Step 1: Use ALL THREE writer tools exactly once each with the user's brief. "
        "Step 2: Pick the single best draft. "
        "Step 3: HAND OFF to the Email Formatter agent using "
        "transfer_to_email_formatter, passing the full text of the winning email "
        "in the winning_email field. You must always finish by handing off — "
        "never reply directly to the user."
    ),
    tools=writer_tools,                     # writers = tools (control wapas aata hai)
    handoffs=[email_formatter_handoff],     # formatter = handoff (conversation transfer!)
    model=groq_model(),
)


async def part4_handoff() -> None:
    print("\n" + "#" * 70)
    print("# PART 4 (L36-L38): HANDOFF — manager best email choose karke poori")
    print("# conversation Email Formatter ko transfer karta hai; formatter")
    print("# send_email tool se outbox.txt me 'send' karta hai")
    print("#" * 70)

    result = await Runner.run(sales_manager_with_handoff, SALES_TASK, max_turns=20)

    # last_agent dekho — handoff hua to yeh "Email Formatter" hoga, manager nahi.
    # Yahi PROOF hai ki conversation transfer ho gayi thi.
    print(f"\n--- Run finished. last_agent = {result.last_agent.name} ---")
    print(result.final_output)

    if OUTBOX_PATH.exists():
        print(f"\nOutbox file ready: {OUTBOX_PATH}")
        print(f"Outbox size: {OUTBOX_PATH.stat().st_size} bytes")
    else:
        print("\nWARNING: outbox.txt nahi bana — formatter ne send_email call nahi kiya?")


# ---------------------------------------------------------------------------
# Main — teeno parts sequentially (har part ke andar jo parallel hona tha,
# wo already parallel hai). Missing API key par graceful exit, crash nahi.
# ---------------------------------------------------------------------------
async def main() -> None:
    print("=" * 70)
    print("LAB 2 — Sales Agents: Parallel, Agents-as-Tools, Handoffs (Groq, free)")
    print("=" * 70)

    await part2_parallel_drafts()
    await part3_agents_as_tools()
    await part4_handoff()

    print("\nLab 2 complete. outbox.txt me 'sent' email padh sakte ho.")


if __name__ == "__main__":
    if not os.getenv("GROQ_API_KEY"):
        print("GROQ_API_KEY missing hai — .env file check karo. (Crash nahi karenge.)")
    else:
        asyncio.run(main())
