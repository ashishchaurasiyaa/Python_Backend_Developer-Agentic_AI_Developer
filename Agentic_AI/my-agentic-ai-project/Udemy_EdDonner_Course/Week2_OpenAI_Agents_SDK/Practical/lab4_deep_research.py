"""
LAB 4 — Mini DEEP RESEARCH Agent = Week 2 ka CAPSTONE (Lectures L42-L48)
=========================================================================

KYA SEEKHENGE (Ed Donner ke deep-research design ka free version):
- L42: Deep Research ka overall architecture — ek topic ko multiple agents
  milkar research karte hain (plan -> search -> write pipeline).
- L43: PLANNER AGENT — structured output (Pydantic WebSearchPlan) se decide
  karta hai ki kaunsi 3 web searches karni hain aur KYUN (reason field).
- L45: SEARCH AGENTS — har planned query ke liye ek summarizer agent jo
  web_search TOOL use karta hai; saare agents asyncio.gather se PARALLEL
  chalte hain (yahi "agentic parallelism" ka core idea hai).
- L44: WRITER AGENT — saari summaries ko ek detailed markdown report me
  convert karta hai (Pydantic ReportData ke saath structured output).
- L46-L47: Optional Gradio UI — same pipeline ko web UI se trigger karna.

COURSE vs HUMARA SETUP:
- Course me OpenAI ka PAID hosted `WebSearchTool` use hota hai (~$0.025/call).
  Hum FREE Wikipedia search API (keyless) se EXACTLY wahi pattern seekh
  rahe hain — tool ka source badla hai, AGENTIC design bilkul same hai.
- Models: free Groq (llama-3.3-70b) primary; structured output ke liye
  fallback ladder (Groq gpt-oss-120b -> Gemini -> manual JSON parse).

KAISE CHALANA HAI:
  cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
  uv run Udemy_EdDonner_Course/Week2_OpenAI_Agents_SDK/Practical/lab4_deep_research.py        # console pipeline + sample_report.md
  uv run Udemy_EdDonner_Course/Week2_OpenAI_Agents_SDK/Practical/lab4_deep_research.py ui     # Gradio UI (L46-L47)
"""

import os
import re
import sys
import json
import asyncio
from pathlib import Path

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from agents import (
    Agent,
    Runner,
    OpenAIChatCompletionsModel,
    function_tool,
    set_tracing_disabled,
)

load_dotenv(override=True)
# Tracing OpenAI platform pe jaata hai; humare paas valid OPENAI_API_KEY nahi hai — isliye OFF.
set_tracing_disabled(True)

# ---------------------------------------------------------------------------
# MODEL HELPERS — Groq aur Gemini dono OpenAI-compatible endpoints dete hain,
# isliye OpenAI Agents SDK me `OpenAIChatCompletionsModel` ke through plug
# ho jaate hain. Yahi Ed Donner wala "use any provider" trick hai.
# ---------------------------------------------------------------------------
GROQ_MODEL = "llama-3.3-70b-versatile"  # free + tool-calling supported


def groq_model(model_name: str = GROQ_MODEL) -> OpenAIChatCompletionsModel:
    client = AsyncOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
    )
    return OpenAIChatCompletionsModel(model=model_name, openai_client=client)


def gemini_model(model_name: str = "gemini-2.5-flash") -> OpenAIChatCompletionsModel:
    client = AsyncOpenAI(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=os.getenv("GOOGLE_API_KEY"),
    )
    return OpenAIChatCompletionsModel(model=model_name, openai_client=client)


# ---------------------------------------------------------------------------
# STEP 1 — SEARCH TOOL (free, keyless)
# Course me OpenAI ka paid WebSearchTool use hota hai — hum FREE Wikipedia
# search API se same "agent ke paas search tool hai" pattern seekh rahe hain.
# @function_tool decorator: function signature + docstring se SDK khud
# JSON schema bana ke LLM ko tool ke roop me expose kar deta hai.
# ---------------------------------------------------------------------------
@function_tool
async def web_search(query: str) -> str:
    """Search the web (Wikipedia) for the given query and return the top
    results as titles with text snippets.

    Args:
        query: The search query to look up.
    """
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": 5,
                    "srprop": "snippet",
                },
                headers={"User-Agent": "AgenticAI-Lab4-DeepResearch/1.0"},
            )
            resp.raise_for_status()
            hits = resp.json().get("query", {}).get("search", [])
            if not hits:
                return f"No results found for query: {query}"
            lines = []
            for hit in hits:
                # Snippet me HTML tags (<span class="searchmatch">) aate hain — strip kar do
                snippet = re.sub(r"<[^>]+>", "", hit.get("snippet", ""))
                lines.append(f"Title: {hit['title']}\nSnippet: {snippet}")
            return "\n\n".join(lines)
    except Exception as exc:
        # Network fail ho to agent ko crash mat karao — string me error batao,
        # LLM khud gracefully handle kar lega.
        return f"SEARCH_ERROR: could not search the web ({exc})"


# ---------------------------------------------------------------------------
# STEP 2 — Pydantic schemas (L43/L44): structured outputs ka backbone.
# output_type=PydanticModel dene se SDK model ko json_schema bhejta hai aur
# result.final_output seedha typed Python object milta hai — string parsing nahi!
# ---------------------------------------------------------------------------
HOW_MANY_SEARCHES = 3


class WebSearchItem(BaseModel):
    reason: str = Field(description="Why this search is important for the research")
    query: str = Field(description="The search term to use for the web search")


class WebSearchPlan(BaseModel):
    searches: list[WebSearchItem] = Field(
        description=f"A list of exactly {HOW_MANY_SEARCHES} web searches to perform"
    )


class ReportData(BaseModel):
    short_summary: str = Field(description="A short 2-3 sentence summary of the findings")
    markdown_report: str = Field(description="The final detailed report in markdown")


# ---------------------------------------------------------------------------
# Agent instructions — Ed ke deep_research repo jaisi hi style
# ---------------------------------------------------------------------------
PLANNER_INSTRUCTIONS = (
    "You are a research planner. Given a research topic, come up with exactly "
    f"{HOW_MANY_SEARCHES} distinct web searches that together would best cover the topic. "
    "For each search give a short reason why it matters."
)

SEARCH_INSTRUCTIONS = (
    "You are a research assistant. Given a search term, use the web_search tool to "
    "search the web, then produce a concise summary of the results in 2-3 paragraphs "
    "(under 300 words). Capture the main points; ignore fluff. This summary will be "
    "consumed by a report writer, so facts matter more than perfect grammar. "
    "If the tool returns SEARCH_ERROR, say what you know about the term from your own "
    "knowledge and clearly note that live search was unavailable."
)

WRITER_INSTRUCTIONS = (
    "You are a senior researcher writing a cohesive report for a research query. "
    "You will be given the original topic and a set of research summaries. "
    "First plan the structure, then write a detailed markdown report with headings. "
    "Aim for 500-1000 words. Include a short 2-3 sentence executive summary."
)


# ---------------------------------------------------------------------------
# STRUCTURED OUTPUT with PROVIDER FALLBACK LADDER:
# Order: (a) Groq llama-3.3 -> (b) Groq openai/gpt-oss-120b -> (c) Gemini
# (OpenAI-compat, json_schema supported) -> (d) last resort: output_type hata
# ke prompt me "respond ONLY with JSON" + manual json parse.
#
# VERIFICATION ME KYA CHALA (real run ka result):
# - Groq llama-3.3: 400 error — "This model does not support response_format
#   json_schema" (yeh model structured output support hi nahi karta).
# - Groq gpt-oss-120b: json_schema accept karta hai par is SDK ke strict
#   schema pe consistently 'json_validate_failed' deta hai.
# - Gemini 2.5-flash: json_schema support karta hai, par free-tier quota
#   exhaust hone par RateLimitError de sakta hai (environmental).
# - FINAL CHOICE jo chali: (d) MANUAL JSON PARSE — prompt me schema daal ke
#   "respond ONLY with JSON" + pydantic model_validate_json. Lesson: ladder
#   isliye rakhi hai taaki jis din Gemini quota wapas aaye, behtar option
#   khud-ba-khud use ho jaye — code change ki zaroorat nahi.
# ---------------------------------------------------------------------------
def _strip_code_fences(text: str) -> str:
    """LLM kabhi-kabhi ```json ... ``` fences me JSON deta hai — unhe hata do."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


async def run_structured(agent_name: str, instructions: str, output_type, user_input: str):
    providers = [
        ("Groq llama-3.3-70b", lambda: groq_model()),
        ("Groq openai/gpt-oss-120b", lambda: groq_model("openai/gpt-oss-120b")),
        ("Gemini gemini-2.5-flash", lambda: gemini_model()),
    ]
    for label, model_factory in providers:
        try:
            agent = Agent(
                name=agent_name,
                instructions=instructions,
                model=model_factory(),
                output_type=output_type,
            )
            result = await Runner.run(agent, user_input)
            print(f"      [provider] {label} -> structured output OK")
            return result.final_output
        except Exception as exc:
            print(f"      [fallback] {label} fail hua ({type(exc).__name__}) -> agla provider")

    # Last resort (fallback d): no output_type, JSON manually parse karo
    schema = json.dumps(output_type.model_json_schema())
    agent = Agent(
        name=f"{agent_name}_json",
        instructions=(
            instructions
            + "\n\nRespond ONLY with a single JSON object matching this JSON schema, "
            "no markdown fences, no extra text:\n" + schema
        ),
        model=groq_model(),
    )
    result = await Runner.run(agent, user_input)
    parsed = output_type.model_validate_json(_strip_code_fences(str(result.final_output)))
    print(f"      [fallback] manual JSON parse se kaam chala (provider ladder exhaust ho gaya)")
    return parsed


# ---------------------------------------------------------------------------
# PIPELINE PHASES
# ---------------------------------------------------------------------------
async def plan_searches(topic: str) -> WebSearchPlan:
    """L43 — PLANNER: topic -> 3 planned searches (structured output)."""
    return await run_structured(
        "PlannerAgent", PLANNER_INSTRUCTIONS, WebSearchPlan, f"Research topic: {topic}"
    )


async def run_one_search(item: WebSearchItem) -> str:
    """L45 — ek SEARCH AGENT: web_search tool + 2-3 paragraph summary.

    NOTE: har call pe FRESH agent banate hain — agents stateless hote hain,
    expensive nahi (sirf config object hai), aur parallel runs me safe.
    """
    search_agent = Agent(
        name="SearchAgent",
        instructions=SEARCH_INSTRUCTIONS,
        tools=[web_search],
        model=groq_model(),
    )
    try:
        result = await Runner.run(
            search_agent, f"Search term: {item.query}\nReason for search: {item.reason}"
        )
        return str(result.final_output)
    except Exception as exc:
        # Ek search fail hone se poora capstone nahi girna chahiye
        return f"(Search for '{item.query}' failed: {type(exc).__name__} — skipping.)"


async def perform_searches(plan: WebSearchPlan) -> list[str]:
    """L45 — saare search agents PARALLEL me: asyncio.gather = fan-out pattern.
    Sequential hota to 3x time lagta; parallel me sab ek saath fire hote hain."""
    tasks = [run_one_search(item) for item in plan.searches]
    return await asyncio.gather(*tasks)


async def write_report(topic: str, summaries: list[str]) -> ReportData:
    """L44 — WRITER: summaries -> detailed markdown report (structured output)."""
    joined = "\n\n".join(
        f"### Research summary {i + 1}\n{s}" for i, s in enumerate(summaries)
    )
    user_input = f"Original research topic: {topic}\n\nSummarized search results:\n{joined}"
    try:
        return await run_structured("WriterAgent", WRITER_INSTRUCTIONS, ReportData, user_input)
    except Exception as exc:
        # Bilkul aakhri bachav: plain markdown agent (no structured output) —
        # report to milni hi chahiye, bhale short_summary topic se bana lein.
        print(f"      [fallback] structured writer fail ({type(exc).__name__}) -> plain markdown writer")
        plain_writer = Agent(
            name="WriterAgentPlain",
            instructions=WRITER_INSTRUCTIONS + " Respond with the markdown report only.",
            model=groq_model(),
        )
        result = await Runner.run(plain_writer, user_input)
        return ReportData(
            short_summary=f"Research report on: {topic}",
            markdown_report=str(result.final_output),
        )


# ---------------------------------------------------------------------------
# STEP 5 — ORCHESTRATION: plan -> parallel search -> write
# Dhyan do: yahan koi "manager LLM" nahi hai — PLAIN PYTHON code hi
# orchestrator hai. Ed isko "agentic workflow" kehte hain: deterministic
# pipeline jisme har step ek agent hai. (Handoffs wala dynamic style alag hai.)
# ---------------------------------------------------------------------------
async def deep_research(topic: str) -> ReportData:
    print(f"\n=== DEEP RESEARCH: {topic} ===")

    print("\n[Phase 1/3] Planning searches (PlannerAgent, structured output)...")
    plan = await plan_searches(topic)
    for i, item in enumerate(plan.searches, 1):
        print(f"   {i}. query='{item.query}'  | reason: {item.reason}")

    print(f"\n[Phase 2/3] Running {len(plan.searches)} search agents in PARALLEL (asyncio.gather)...")
    summaries = await perform_searches(plan)
    for i, s in enumerate(summaries, 1):
        print(f"   Summary {i}: {len(s)} chars -> '{s[:80].replace(chr(10), ' ')}...'")

    print("\n[Phase 3/3] Writing final report (WriterAgent)...")
    report = await write_report(topic, summaries)
    print(f"   Short summary: {report.short_summary}")
    print(f"   Markdown report: {len(report.markdown_report)} chars")
    return report


# ---------------------------------------------------------------------------
# STEP 6 — OPTIONAL GRADIO UI (L46-L47): same pipeline, web UI se.
# Gradio async functions ko natively support karta hai — direct await!
# ---------------------------------------------------------------------------
def launch_ui():
    import gradio as gr

    async def run_research(topic: str) -> str:
        if not topic or not topic.strip():
            return "Please enter a research topic."
        try:
            report = await deep_research(topic.strip())
            return report.markdown_report
        except Exception as exc:
            return f"Research failed: {type(exc).__name__}: {exc}"

    with gr.Blocks(title="Mini Deep Research") as demo:
        gr.Markdown("# Mini Deep Research Agent\nPlan -> Parallel Search -> Report (free Groq + Wikipedia)")
        topic_box = gr.Textbox(label="Research topic", placeholder="e.g. The future of electric vehicles in India")
        run_btn = gr.Button("Run Deep Research", variant="primary")
        report_md = gr.Markdown(label="Report")
        run_btn.click(fn=run_research, inputs=topic_box, outputs=report_md)
        topic_box.submit(fn=run_research, inputs=topic_box, outputs=report_md)

    demo.launch()


# ---------------------------------------------------------------------------
# MAIN — default: console pipeline (non-interactive, verification-friendly);
# 'ui' argument do to Gradio UI launch hota hai.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if not os.getenv("GROQ_API_KEY"):
        print("GROQ_API_KEY missing hai — .env file check karo. (Crash nahi, bas exit.)")
        sys.exit(0)

    if "ui" in sys.argv[1:]:
        launch_ui()
    else:
        demo_topic = "The history and impact of the Apollo 11 Moon landing"
        report = asyncio.run(deep_research(demo_topic))

        out_path = Path(__file__).parent / "sample_report.md"
        out_path.write_text(
            f"# Deep Research Report\n\n**Topic:** {demo_topic}\n\n"
            f"**Executive summary:** {report.short_summary}\n\n---\n\n"
            f"{report.markdown_report}\n",
            encoding="utf-8",
        )
        print(f"\nReport saved -> {out_path}")
        print("\nTip: Gradio UI ke liye chalao:  uv run .../lab4_deep_research.py ui")
