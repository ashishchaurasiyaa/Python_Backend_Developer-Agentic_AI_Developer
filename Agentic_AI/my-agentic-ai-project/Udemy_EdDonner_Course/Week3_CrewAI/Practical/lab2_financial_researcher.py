"""
LAB 2 — Financial Researcher Crew: Custom Tools + Task Context + output_file (L55-L57)
=======================================================================================

KYA SEEKHENGE:
  1. CUSTOM TOOL banana — `crewai.tools.BaseTool` subclass karke, pydantic `args_schema`
     ke saath. Course (Ed Donner) me SerperDevTool use hota hai (Google search — PAID
     API key chahiye). Hum FREE Wikipedia API use kar rahe hain via httpx — concept
     bilkul same hai: LLM ka knowledge-cutoff problem (L57) solve karne ke liye usse
     fresh/external data ek TOOL ke through do, taaki wo hallucinate na kare.
  2. Agent ko tool dena: `Agent(tools=[wiki_tool])` — agent khud decide karta hai kab
     aur kitni baar tool call karna hai (ReAct-style loop internally).
  3. TASK CONTEXT CHAINING: `Task(context=[research_task])` — Analyst ko Researcher ka
     poora output milta hai as context. Sequential process me ye explicit chaining
     zyada reliable hai.
  4. `output_file` param: Task apna final output seedha disk pe likh deta hai —
     report generation pipelines ka bread-and-butter.

COURSE NOTE: Ed course me crew YAML config se banta hai (agents.yaml / tasks.yaml +
@CrewBase, @agent, @task decorators) — production projects me wahi pattern accha hai.
Ye lab self-contained code-style me hai taaki saare concepts ek file me dikhein.

KAISE CHALANA:
  cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
  uv run Udemy_EdDonner_Course/Week3_CrewAI/Practical/lab2_financial_researcher.py

LECTURES: L55 (custom tools), L56 (financial researcher crew), L57 (knowledge cutoff
aur search tools se fresh data).
"""

import os
import re
import time

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import BaseTool

# ---------------------------------------------------------------------------
# Setup: env + telemetry band (speed + privacy)
# ---------------------------------------------------------------------------
load_dotenv(override=True)
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

# Paths: CrewAI ka output_file validator ABSOLUTE path ka leading "/" STRIP kar
# deta hai (path-traversal security check) — isliye hum script ke dir me chdir
# karke RELATIVE path "output/financial_report.md" dete hain. Net result wahi
# exact absolute location hai.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
REPORT_PATH = os.path.join(OUTPUT_DIR, "financial_report.md")


# ---------------------------------------------------------------------------
# STEP 1 — CUSTOM TOOL (L55/L57)
# ---------------------------------------------------------------------------
# Course me: from crewai_tools import SerperDevTool (Google search, paid SERPER_API_KEY).
# Hum free Wikipedia API use kar rahe — knowledge-cutoff problem ka SAME solution:
# LLM ko external/fresh data tool se milta hai, training data pe depend nahi karta.
#
# BaseTool ke 3 mandatory parts:
#   - name + description: ye LLM ke prompt me jaate hain — LLM inhi se decide karta
#     hai ki tool kab call karna hai. Description jitni clear, tool use utna sahi.
#   - args_schema: pydantic model — LLM ko EXACT input format batata hai (function
#     calling ka JSON schema isi se banta hai).
#   - _run(): actual Python execution — yahan koi LLM nahi, pure code.


class WikipediaSearchInput(BaseModel):
    """Tool ka input schema — LLM isi shape me arguments generate karega."""

    query: str = Field(
        ...,
        description="Search term, e.g. a company name like 'Tesla, Inc.' or 'Tesla Model 3 sales'",
    )


class WikipediaSearchTool(BaseTool):
    name: str = "Wikipedia Search"
    description: str = (
        "Searches Wikipedia and returns the top 3 matching articles with their "
        "title, search snippet and intro extract. Use this to research companies, "
        "their history, products and recent events with factual, up-to-date data."
    )
    args_schema: type[BaseModel] = WikipediaSearchInput

    def _run(self, query: str) -> str:
        api = "https://en.wikipedia.org/w/api.php"
        # Wikipedia etiquette: descriptive User-Agent dena chahiye warna 403 mil sakta hai
        headers = {"User-Agent": "CrewAI-Lab2-FinancialResearcher/1.0 (learning project)"}

        try:
            with httpx.Client(headers=headers, timeout=20.0) as client:
                # Call 1: action=query&list=search — top 3 results (title + snippet)
                search_resp = client.get(
                    api,
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": query,
                        "srlimit": 3,
                        "format": "json",
                    },
                )
                search_resp.raise_for_status()
                hits = search_resp.json().get("query", {}).get("search", [])
                if not hits:
                    return f"No Wikipedia results found for '{query}'. Try a different query."

                titles = [h["title"] for h in hits]

                # Call 2: prop=extracts — har article ka plain-text intro paragraph
                # (snippet chhota hota hai, extract se LLM ko solid context milta hai)
                extract_resp = client.get(
                    api,
                    params={
                        "action": "query",
                        "prop": "extracts",
                        "exintro": 1,
                        "explaintext": 1,
                        "titles": "|".join(titles),
                        "format": "json",
                    },
                )
                extract_resp.raise_for_status()
                pages = extract_resp.json().get("query", {}).get("pages", {})
                extracts = {p.get("title", ""): p.get("extract", "") for p in pages.values()}
        except httpx.HTTPError as e:
            # Tool kabhi crash nahi hona chahiye — error string return karo, LLM
            # usko padh ke retry / alternate query try kar sakta hai.
            return f"Wikipedia API error: {e}. Try again or use a different query."

        # Top 3 results format karo — snippet me HTML tags hote hain, strip karo.
        # Extract ko ~1200 chars pe cap karo taaki Groq free-tier ka token budget na phate.
        blocks = []
        for i, hit in enumerate(hits, start=1):
            title = hit["title"]
            snippet = re.sub(r"<[^>]+>", "", hit.get("snippet", ""))
            extract = (extracts.get(title) or "").strip()[:1200]
            blocks.append(
                f"RESULT {i}: {title}\nSnippet: {snippet}\nExtract: {extract or '(no extract)'}"
            )
        return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# STEP 2 — Crew banana: Researcher (with tool) -> Analyst (with context)
# ---------------------------------------------------------------------------


def build_crew() -> Crew:
    # NOTE: CrewAI normally LiteLLM ke through LLM(model="groq/llama-3.3-70b-versatile")
    # leta hai, par is env me litellm installed NAHI hai (crewai 1.14.5 native
    # providers only). Trick: Groq ka API OpenAI-COMPATIBLE hai — to hum crewai ka
    # NATIVE "openai" provider use karte hain (explicit provider= kwarg zaroori hai,
    # warna router model-name ko OpenAI ke known models se validate karke reject kar
    # deta hai) aur base_url Groq pe point kar dete hain. Same free GROQ_API_KEY.
    groq_llm = LLM(
        model="llama-3.3-70b-versatile",
        provider="openai",
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
    )

    wiki_tool = WikipediaSearchTool()

    # AGENT 1 — Researcher: tools=[wiki_tool] dene se LLM ke prompt me tool ka
    # name/description/schema inject hota hai; agent ReAct loop me tool call karta hai.
    researcher = Agent(
        role="Senior Financial Researcher",
        goal="Gather accurate, factual information about {company} using the Wikipedia Search tool",
        backstory=(
            "You are a meticulous researcher at a financial intelligence firm. "
            "You never rely on memory alone — you always verify facts using your "
            "search tool, running multiple targeted searches (company overview, "
            "history, recent events) before concluding."
        ),
        tools=[wiki_tool],  # <-- yahi tool-binding hai
        llm=groq_llm,
        max_iter=6,  # tool-call loop ki upper limit — runaway loops/rate-limits se bachao
        verbose=True,
    )

    # AGENT 2 — Analyst: koi tool nahi — iska kaam sirf Researcher ke findings ko
    # ek polished report me convert karna hai (separation of concerns).
    analyst = Agent(
        role="Financial Report Analyst",
        goal="Turn raw research about {company} into a clear, well-structured markdown report",
        backstory=(
            "You are a senior analyst known for crisp, structured markdown reports. "
            "You only use the research given to you — you never invent facts, and "
            "you always include a compliance disclaimer."
        ),
        llm=groq_llm,
        verbose=True,
    )

    # TASK 1 — research: description me explicitly bolo tool USE karo (L57 lesson:
    # bina tool ke LLM stale/hallucinated data dega).
    research_task = Task(
        description=(
            "Research the company {company}. You MUST use the Wikipedia Search tool "
            "(do NOT answer from memory). Run 2-3 searches, e.g. '{company}', "
            "'{company} history', '{company} recent events'. Collect: what the "
            "company does, key history/milestones, notable recent events, and "
            "anything relevant to its business outlook."
        ),
        expected_output=(
            "Detailed research notes (bullet points) about {company} covering "
            "overview, history, recent events and outlook-relevant facts, based "
            "on the tool results."
        ),
        agent=researcher,
    )

    # TASK 2 — report: context=[research_task] se Researcher ka POORA output is
    # task ke prompt me aata hai. output_file se final report disk pe save hoti hai.
    report_task = Task(
        description=(
            "Using the research notes provided, write a structured markdown report "
            "on {company} with EXACTLY these sections:\n"
            "# {company} — Financial Research Report\n"
            "## Company Overview\n## History\n## Recent Events\n## Outlook\n"
            "End with this disclaimer (as a blockquote): 'This report is for "
            "educational purposes only and is not intended for trading decisions.'"
        ),
        expected_output="A complete markdown report on {company} with the five required parts.",
        agent=analyst,
        context=[research_task],  # <-- explicit context chaining
        output_file="output/financial_report.md",  # relative path (validator absolute "/" strip karta hai)
    )

    return Crew(
        agents=[researcher, analyst],
        tasks=[research_task, report_task],
        process=Process.sequential,
        verbose=True,
    )


# ---------------------------------------------------------------------------
# STEP 3 — Run with retry (Groq free tier kabhi-kabhi transient/rate-limit errors deta hai)
# ---------------------------------------------------------------------------


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.chdir(BASE_DIR)  # taaki output_file ka relative path exact target pe lande

    company = "Tesla"
    crew = build_crew()

    result = None
    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            result = crew.kickoff(inputs={"company": company})
            break
        except Exception as e:  # noqa: BLE001 — free-tier 429/5xx ke liye blanket retry
            last_err = e
            print(f"\n[Attempt {attempt}/3 failed: {e}] — 20s ruk ke retry...\n")
            time.sleep(20)

    print("\n" + "=" * 70)
    print("LAB 2 SUMMARY — Financial Researcher Crew")
    print("=" * 70)
    if result is None:
        print(f"Crew FAILED after 3 attempts: {last_err}")
        return

    if os.path.exists(REPORT_PATH):
        size = os.path.getsize(REPORT_PATH)
        print(f"Report saved via output_file -> {REPORT_PATH} ({size} bytes)")
        with open(REPORT_PATH, encoding="utf-8") as f:
            preview = f.read(400)
        print("--- Report preview (first 400 chars) ---")
        print(preview)
    else:
        print("WARNING: report file not found — output_file path check karo!")

    print("--- Final crew output (last 300 chars) ---")
    print(result.raw[-300:])


if __name__ == "__main__":
    main()
