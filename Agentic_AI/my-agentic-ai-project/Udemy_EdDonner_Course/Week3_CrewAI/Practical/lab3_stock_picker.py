"""
LAB 3 — Stock Picker: Structured Outputs (output_pydantic) + Custom Tools  (Lectures L58-L60)
=============================================================================================

KYA SEEKHENGE (CrewAI ke 2 power-features, Ed Donner course Week 3):

1) STRUCTURED OUTPUTS (L59):
   - Ab tak tasks ka output sirf raw TEXT tha — LLM jo bole wahi string.
   - Task(..., output_pydantic=MyModel) dene se CrewAI LLM ko FORCE karta hai ki
     final answer us Pydantic schema ke JSON me aaye, phir use parse karke
     `task.output.pydantic` / `result.pydantic` me TYPED OBJECT de deta hai.
   - Matlab downstream code me `picked.chosen.investment_potential_score` jaisa
     dot-access milta hai — string parsing / regex ka jhanjhat khatam.
   - Ye production me CRITICAL hai: agents ka output aage API/DB me jaata hai,
     wahan free-text nahi chalta.

2) CUSTOM TOOLS (L60):
   - crewai.tools.BaseTool subclass karo: name + description + args_schema
     (pydantic) + _run() method. Bas — agent ko tools=[...] me de do.
   - description + args_schema hi LLM ko batate hain ki tool KAB aur KAISE
     call karna hai (ye prompt me inject hote hain) — isliye inhe achha likhna
     utna hi zaroori hai jitna code.
   - Course me Ed Pushover se phone-push bhejta hai (Week 1 jaisa hi).
     Humne wahi pattern rakha: PUSHOVER_TOKEN/PUSHOVER_USER env me ho to httpx
     POST, warna console print + output/notifications.log me append (no crash).

3) CREW DESIGN (L58 — Stock Picker project):
   sector input --> [Trend Finder] 3 trending companies (TrendingCompanyList)
                --> [Researcher]   detailed research text (context=task1)
                --> [Stock Picker] best pick decide + PUSH NOTIFICATION (tool!)
                --> [Formatter]    final typed answer (PickedStock)
   - Task chaining `context=[...]` se hota hai (Lab 2 me dekha tha).
   - "Pick" aur "Format" alag tasks kyun? GROQ API LIMITATION (lab-tested):
     ek hi request me tools + response_format(json) DONO nahi ja sakte —
     400 error: "json mode cannot be combined with tool/function calling".
     CrewAI output_pydantic wale task ki HAR LLM call me response_format
     bhejta hai, to tool-wale agent ke saath combine karna Groq par crash
     karta hai. Solution = classic "ACT then FORMAT" two-step pattern
     (production me bhi common: pehle side-effects, phir structured output).
   - COURSE NOTE: Ed course me ye sab YAML config se hota hai
     (config/agents.yaml + config/tasks.yaml + @CrewBase/@agent/@task
     decorators) — hamare labs self-contained code-style me hain taaki ek hi
     file me poora picture dikhe; concepts 100% same hain.

KAISE CHALANA:
    cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
    uv run Udemy_EdDonner_Course/Week3_CrewAI/Practical/lab3_stock_picker.py

REQUIREMENTS: .env me GROQ_API_KEY (free tier chalega). Pushover optional.

DISCLAIMER (zaroori!): Ye PURELY EDUCATIONAL lab hai — LLM ke paas na real-time
market data hai na koi financial expertise guarantee. Iska output REAL
INVESTMENT ADVICE NAHI hai. Paisa lagane se pehle SEBI-registered advisor se
milo, LLM se nahi. :)
"""

import os
import time

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# .env pehle load karo (override=True => .env shell env ko beat karega)
load_dotenv(override=True)

# Telemetry band — speed + privacy (CrewAI by default anonymized telemetry bhejta hai)
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import httpx
from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import BaseTool

# Notifications fallback log file (Pushover na ho to yahan append hota hai)
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
NOTIF_LOG = os.path.join(OUTPUT_DIR, "notifications.log")


# =============================================================================
# PART 1 — PYDANTIC OUTPUT MODELS (L59)
# =============================================================================
# Field(description=...) sirf documentation nahi hai — CrewAI ye descriptions
# LLM ko JSON-schema ke saath bhejta hai, to jitni clear description, utna
# accurate structured output. (Pydantic yahan double duty kar raha hai:
# LLM-guidance + runtime validation.)

class TrendingCompany(BaseModel):
    """Ek trending company — Trend Finder agent isse 3 baar bharega."""
    name: str = Field(description="Company ka poora naam")
    ticker: str = Field(description="Stock ticker symbol, e.g. NVDA")
    reason: str = Field(description="Ye company abhi trending/interesting kyun hai (1-2 lines)")


class TrendingCompanyList(BaseModel):
    """Task 1 ka structured output — list wrapper.
    NOTE: CrewAI me top-level output hamesha ek single model hota hai,
    isliye `list[TrendingCompany]` ko is wrapper me lapeta hai."""
    companies: list[TrendingCompany] = Field(description="Exactly 3 trending companies")


class ResearchedCompany(BaseModel):
    """Ek researched company — Stock Picker iska use final pick me karega."""
    name: str = Field(description="Company ka naam")
    market_position: str = Field(description="Market me company ki current position/standing")
    future_outlook: str = Field(description="Aage ka outlook — growth drivers aur risks")
    investment_potential_score: int = Field(
        description="Investment potential score, 1 (worst) se 10 (best) — int hi dena"
    )


class PickedStock(BaseModel):
    """Task 3 ka final structured output — typed final answer!"""
    chosen: ResearchedCompany = Field(description="Best pick — full researched details ke saath")
    rationale: str = Field(description="Ye company kyun choose hui — clear reasoning")
    runners_up: list[str] = Field(description="Baaki companies ke naam jo choose NAHI hue")


# =============================================================================
# PART 2 — CUSTOM PUSH NOTIFICATION TOOL (L60)
# =============================================================================

class PushNotificationInput(BaseModel):
    """Tool ka input schema — LLM isi shape me arguments generate karega."""
    message: str = Field(description="User ko bhejne wala short notification message")


class PushNotificationTool(BaseTool):
    """Pushover push notification tool — Week 1 ke career-agent jaisa hi pattern.

    COURSE NOTE: Ed ke course me Pushover hi use hota hai (free app + API).
    Hamara twist: agar PUSHOVER_TOKEN/PUSHOVER_USER env me NAHI hain to bhi
    lab crash nahi karta — console pe print + notifications.log me append
    (graceful fallback). Tool kabhi exception ke saath crew ko nahi girata.
    """

    # Ye 3 cheezein LLM ke prompt me jaati hain — tool ka "resume" samjho:
    name: str = "send_push_notification"
    description: str = (
        "User ke phone par ek short push notification bhejta hai. "
        "Jab final stock pick decide ho jaye, tab is tool se user ko "
        "ek-line summary (company + reason) notify karo."
    )
    args_schema: type[BaseModel] = PushNotificationInput

    def _run(self, message: str) -> str:
        token = os.getenv("PUSHOVER_TOKEN")
        user = os.getenv("PUSHOVER_USER")

        if token and user:
            # Real Pushover push (project rule: 'requests' nahi, httpx)
            try:
                resp = httpx.post(
                    "https://api.pushover.net/1/messages.json",
                    data={"token": token, "user": user, "message": message},
                    timeout=10,
                )
                resp.raise_for_status()
                return f"Push notification sent via Pushover: {message}"
            except Exception as e:
                # Network fail ho to bhi crew nahi tootni chahiye — fallback pe gir jao
                print(f"[push] Pushover error (fallback to log): {e}")

        # FALLBACK: silent no-op style — console + log file, NO crash
        print(f"\n[PUSH NOTIFICATION] {message}\n")
        try:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            with open(NOTIF_LOG, "a") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {message}\n")
        except Exception:
            pass  # logging fail ho jaye to bhi chup-chaap aage badho
        return f"Notification delivered (console + log fallback): {message}"


# =============================================================================
# PART 3 — AGENTS + TASKS + CREW (sab Groq free tier par)
# =============================================================================

def build_crew() -> tuple[Crew, Task, Task, Task, Task]:
    # LLM SETUP NOTE: purane CrewAI versions me LiteLLM built-in tha to
    # LLM(model="groq/llama-3.3-70b-versatile") seedha chal jaata tha.
    # CrewAI 1.14.x me native providers hain (openai/anthropic/gemini/...) aur
    # litellm OPTIONAL extra hai — humne extra dependency nahi badhayi, kyunki
    # Groq ka API OpenAI-COMPATIBLE hai: native "openai" provider ko explicit
    # provider= kwarg + Groq ka base_url + GROQ_API_KEY de do, kaam khatam.
    # (provider= explicit dena zaroori hai — "openai/llama..." prefix-format
    # me CrewAI model ko OpenAI ki known-models list se validate karta hai
    # aur llama wahan nahi milta.) Same trick kisi bhi OpenAI-compatible
    # host (Together, Fireworks, vLLM...) ke saath chalta hai.
    groq_llm = LLM(
        model="llama-3.3-70b-versatile",
        provider="openai",                                # native OpenAI client use karo...
        base_url="https://api.groq.com/openai/v1",        # ...par requests Groq ko bhejo
        api_key=os.getenv("GROQ_API_KEY"),
    )

    # STRUCTURED-OUTPUT LLM (lab-tested fact!): output_pydantic ke liye CrewAI
    # OpenAI ka response_format=json_schema bhejta hai. Groq par llama-3.3-70b
    # ye SUPPORT NAHI karta — humne try kiya, har baar 400 error aaya:
    #   "This model does not support response format `json_schema`"
    # Isliye structured tasks (task1 & task3) wale agents ke liye Groq ka
    # "openai/gpt-oss-120b" model use kiya (Groq par OpenAI ka open-weights
    # model, json_schema + tool-calling dono supported) — YE CHALA. Researcher
    # plain-text task hai to wo llama-3.3 par hi theek hai. Lesson: model
    # capability (structured output / tool support) check karna utna hi
    # zaroori hai jitna quality.
    groq_structured_llm = LLM(
        model="openai/gpt-oss-120b",                      # Groq ka model id hi aisa hai
        provider="openai",
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
    )

    push_tool = PushNotificationTool()

    # --- AGENT 1: Trend Finder ---------------------------------------------
    # role-goal-backstory = CrewAI ka prompting framework (system prompt isi
    # se banta hai). {sector} placeholder kickoff(inputs=...) se interpolate hota hai.
    trend_finder = Agent(
        role="Financial Trend Finder",
        goal="{sector} sector me abhi ki 3 sabse trending/interesting companies identify karna",
        backstory=(
            "You are a sharp market-watcher who tracks news, earnings and product "
            "launches. You surface companies that are generating real buzz, with "
            "crisp one-line reasons. You rely on your general knowledge (no live data)."
        ),
        llm=groq_structured_llm,  # task1 me output_pydantic hai => json_schema-capable model
        verbose=True,
    )

    # --- AGENT 2: Researcher -------------------------------------------------
    researcher = Agent(
        role="Equity Research Analyst",
        goal="Trending companies ka deep-dive research karke comparable analysis dena",
        backstory=(
            "You are a meticulous analyst. For each company you assess market "
            "position, competitive moat, future outlook and risks, and assign an "
            "investment potential score from 1 to 10. Balanced, never hype-driven."
        ),
        llm=groq_llm,
        verbose=True,
    )

    # --- AGENT 3: Stock Picker (custom tool ke saath!) ----------------------
    stock_picker = Agent(
        role="Stock Picker",
        goal="Research ke base par single best stock choose karna aur user ko push notification se inform karna",
        backstory=(
            "You are a decisive portfolio manager. You weigh the research, pick "
            "exactly ONE best company, justify it, and ALWAYS notify the user "
            "via the push notification tool before giving your final answer."
        ),
        llm=groq_structured_llm,  # gpt-oss-120b: Groq par reliable tool-calling
        tools=[push_tool],  # <-- custom tool yahan attach hota hai
        verbose=True,
    )

    # --- AGENT 4: Formatter (NO tools — isi liye alag agent hai!) -----------
    # IMPORTANT GOTCHA (lab-tested): agar tools wale agent ko output_pydantic
    # task dete to CrewAI har call me tools + response_format saath bhejta
    # aur Groq 400 deta ("json mode cannot be combined with tool calling").
    # Tool-free agent => sirf response_format jaata hai => clean structured output.
    formatter = Agent(
        role="Investment Report Formatter",
        goal="Stock picker ke decision ko exact structured schema me convert karna",
        backstory=(
            "You convert investment decisions into precise structured records. "
            "You never change the decision — you only restructure the information "
            "faithfully into the requested fields."
        ),
        llm=groq_structured_llm,  # output_pydantic => json_schema-capable model
        verbose=True,
    )

    # --- TASK 1: trending companies (STRUCTURED: TrendingCompanyList) -------
    task_find = Task(
        description=(
            "Find exactly 3 trending / interesting publicly-listed companies in the "
            "{sector} sector right now. For each give the company name, its stock "
            "ticker, and a 1-2 line reason why it is trending."
        ),
        expected_output="A structured list of exactly 3 trending companies with name, ticker and reason.",
        agent=trend_finder,
        output_pydantic=TrendingCompanyList,  # <-- L59 ka hero: typed output!
    )

    # --- TASK 2: research (plain text — har task ko pydantic nahi chahiye) --
    task_research = Task(
        description=(
            "Take the list of trending companies and write a detailed research note "
            "on EACH one: market position, future outlook (growth drivers + risks), "
            "and an investment potential score from 1 to 10. Compare them at the end."
        ),
        expected_output=(
            "A detailed research report covering each company's market position, "
            "future outlook and a 1-10 investment potential score, plus a comparison."
        ),
        agent=researcher,
        context=[task_find],  # task1 ka output is task ke prompt me inject hoga
    )

    # --- TASK 3: pick + notify (TOOL USE — plain text output) ---------------
    # NOTE: yahan output_pydantic NAHI hai — tool-calling task par Groq
    # response_format allow nahi karta (upar wala "ACT then FORMAT" note).
    task_pick = Task(
        description=(
            "Based on the research, choose the single BEST company to (hypothetically) "
            "invest in. FIRST call the send_push_notification tool with a one-line "
            "message like 'Stock pick: <name> (<ticker>) — <short reason>'. THEN state "
            "your final decision with: the chosen company's name, market position, "
            "future outlook, investment potential score (1-10), your rationale, and "
            "the names of the runner-up companies that were not chosen. "
            "This is an educational exercise, not real financial advice."
        ),
        expected_output=(
            "Confirmation that the push notification was sent, followed by the chosen "
            "company with details, score, rationale, and runner-up names."
        ),
        agent=stock_picker,
        context=[task_find, task_research],  # dono pichhle tasks ka output milega
    )

    # --- TASK 4: format (STRUCTURED: PickedStock — final typed answer) ------
    task_format = Task(
        description=(
            "Convert the stock picker's final decision into the structured format. "
            "Do NOT change the decision. Fill in: chosen (name, market_position, "
            "future_outlook, investment_potential_score 1-10), rationale, and "
            "runners_up (names of companies not chosen)."
        ),
        expected_output="The structured final pick exactly matching the schema.",
        agent=formatter,
        context=[task_research, task_pick],  # research detail + final decision
        output_pydantic=PickedStock,  # <-- LAST task ka pydantic == result.pydantic
    )

    crew = Crew(
        agents=[trend_finder, researcher, stock_picker, formatter],
        tasks=[task_find, task_research, task_pick, task_format],
        process=Process.sequential,  # order: find -> research -> pick+notify -> format
        verbose=True,
    )
    return crew, task_find, task_research, task_pick, task_format


# =============================================================================
# PART 4 — MAIN (retry wrapper + typed-output ka clean use)
# =============================================================================

def kickoff_with_retry(crew: Crew, inputs: dict, attempts: int = 3):
    """Free Groq tier kabhi-kabhi rate-limit/transient error deta hai —
    isliye simple retry loop (course me ye nahi sikhaya, par real life me zaroori)."""
    last_err: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            return crew.kickoff(inputs=inputs)
        except Exception as e:
            last_err = e
            print(f"\n[retry] Attempt {i}/{attempts} fail hua: {e}")
            if i < attempts:
                wait = 15 * i
                print(f"[retry] {wait}s ruk ke dobara try karte hain...")
                time.sleep(wait)
    raise RuntimeError(f"Crew {attempts} attempts ke baad bhi fail: {last_err}")


def main() -> None:
    if not os.getenv("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY .env me nahi mila — lab nahi chal sakta.")
        return

    print("=" * 70)
    print("LAB 3 — STOCK PICKER (structured outputs + custom push tool)")
    print("DISCLAIMER: Educational demo only — REAL investment advice NAHI hai!")
    pushover_on = bool(os.getenv("PUSHOVER_TOKEN") and os.getenv("PUSHOVER_USER"))
    print(f"Pushover: {'ON (real push jayega)' if pushover_on else 'OFF (console + log fallback)'}")
    print("=" * 70)

    crew, task_find, _task_research, _task_pick, _task_format = build_crew()

    # {sector} placeholder yahan se bharta hai — same crew ko alag sectors
    # ke liye reuse kar sakte ho (e.g. "Indian EV", "semiconductors", ...)
    result = kickoff_with_retry(crew, inputs={"sector": "Artificial Intelligence"})

    # ---------------- TYPED OUTPUT ka asli maza ----------------
    # result.pydantic == AAKHRI task ka parsed object (PickedStock instance).
    # Har task ka apna bhi hota hai: task.output.pydantic
    picked = result.pydantic
    print("\n" + "=" * 70)
    print("FINAL RESULT (typed Pydantic objects se — koi string parsing nahi!)")
    print("=" * 70)
    print(f"result.pydantic ka type     : {type(picked).__name__}")  # verify: PickedStock

    if isinstance(picked, PickedStock):
        chosen = picked.chosen  # nested typed object — dot access, autocomplete-friendly
        print(f"CHOSEN COMPANY              : {chosen.name}")
        print(f"INVESTMENT POTENTIAL SCORE  : {chosen.investment_potential_score}/10")
        print(f"MARKET POSITION             : {chosen.market_position[:160]}...")
        print(f"FUTURE OUTLOOK              : {chosen.future_outlook[:160]}...")
        print(f"RATIONALE                   : {picked.rationale[:300]}")
        print(f"RUNNERS-UP                  : {', '.join(picked.runners_up)}")
    else:
        # Pydantic parse fail hua to raw text to phir bhi available hai
        print("WARN: pydantic parse nahi hua — raw output dikha rahe hain:")
        print(str(result.raw)[:500])

    # Task 1 ka structured output bhi inspect karo (intermediate task se bhi milta hai)
    trending = task_find.output.pydantic if task_find.output else None
    if isinstance(trending, TrendingCompanyList):
        names = ", ".join(f"{c.name} ({c.ticker})" for c in trending.companies)
        print(f"\nTask1 typed output ({type(trending).__name__}): {names}")

    if not pushover_on:
        print(f"\nNotification log file: {NOTIF_LOG}")
    print("\nLab 3 complete! Agla padav: hierarchical process + memory (Lab 4).")


if __name__ == "__main__":
    main()
