"""
LAB 1 — THE CAPSTONE CORE: "ALEX" multi-agent financial planner (orchestration + structured handoff)
====================================================================================================
Title: Week 4 ka CAPSTONE ka DIL. "ALEX" (Agentic Learning Equities eXplainer) — ek multi-agent
       financial planner jahaan 4 SPECIALIZED agents ek user ki financial profile par COLLABORATE
       karte hain. Har agent ek FOCUSED-role LLM call hai jo ek PYDANTIC-typed result return karta
       hai (string-parsing NAHI). Ek ORCHESTRATOR unhe ek WORKFLOW me chalata hai:
           PlannerAgent  ->  (PortfolioAnalystAgent + RiskAgent)  ->  SynthesizerAgent
       aur har step ka STRUCTURED context agle agent ko handoff karta hai (= context engineering).
       Bina kisi LLM key / boto3 / langfuse / AWS ke bhi pura chalta hai aur EXIT 0 karta hai
       (har agent ek deterministic TEMPLATED stub deta hai taaki orchestration ka SHAPE dikhe).

KYA SEEKHENGE (what concepts):
- MULTI-AGENT vs SINGLE-AGENT (L89): ek "single agent with loop" (Claude Code style) ek hi LLM +
  lambi prompt hota hai. MULTI-AGENT me ek PLANNER/orchestrator alag-alag WORKER agents ko coordinate
  karta hai, har worker ko apna SCOPED context + role-prompt deke. Role split KAB help karta hai:
  jab ek sub-task ki quality alag se MEASURE + IMPROVE karni ho (Ed: "retirement weak laga? usse alag
  LLM call me todo, explicit context+examples do"). Decoupled = independently build/test/evaluate (L90).
  Golden rule (L89): START SIMPLE (1 call), metric measure karo, ZAROORAT par hi agents break-out karo.
- CONTEXT ENGINEERING (L95 — Schmid/Karpathy): "the discipline of designing dynamic systems that
  provide the right information and tools, in the right format, at the right time." Yahan HAR agent
  ko sirf utna hi context milta hai jitna uske task ke liye chahiye:
    * Planner  -> sirf goal + ek light profile-summary (kya analyze karna hai decide kare).
    * Analyst  -> full holdings + plan ke analysis sub-tasks (allocation math kare).
    * Risk     -> full holdings + analyst ke ALLOCATION output (concentration/red-flags dhundhe).
    * Synth    -> sab upstream STRUCTURED outputs (merge karke final rebalancing recommendation de).
  WHY structured (pydantic, na ki free text): agent-to-agent HANDOFF reliable ho — Synth ko Analyst
  ka `top_holding_pct` ek float chahiye, ek paragraph parse nahi karna. Typed handoff = production trust.
- STRUCTURED OUTPUTS (L97/L98 — tagger ka `output_type=PydanticModel`): LLM ko force karte hain ek
  defined JSON schema follow kare. Yahan hum OpenAI-compatible `response_format={"type":"json_object"}`
  + pydantic `model_validate_json` se wahi karte hain (provider-agnostic). Free-text parsing = bug farm.
- DEPLOYABLE SaaS CAPSTONE (L90): yeh ALEX hi wo subscription product hai jise users apne brokerage/
  stock details dete hain aur concentration-risk + rebalancing advice paate hain. Prod me har agent ek
  Lambda (Bedrock via LiteLLM), data Aurora Serverless v2 me, observability Langfuse/CloudWatch me.
- GRACEFUL DEGRADE / OFFLINE-FIRST (Weeks 1-3 ki proven convention): koi LLM key na ho -> har agent ek
  DETERMINISTIC templated stub deta hai (asli LLM nahi, par typed output SAME shape ka) -> orchestration
  visible, exit 0. Aurora = lazy boto3 RDS Data API jab DB_CLUSTER_ARN set; warna stdlib sqlite3 (same
  repository interface). Langfuse = lazy import jab keys set; warna local JSON span-logger (no network).

KAISE CHALANA (how to run) — CWD = repo root:
    # Default: self-demo. No key / no boto3 / no langfuse / no AWS bhi chalega, EXIT 0.
    uv run Udemy_EdDonner_ProductionTrack/Week4_MultiAgent_Observability_AgentCore/Practical/lab1_alex_multiagent_financial_planner.py

    # Apni profile pass karni ho (ek inline JSON):
    uv run .../lab1_alex_multiagent_financial_planner.py --profile '{"name":"X","age":40,"holdings":[{"ticker":"AAPL","value":50000,"asset_class":"equity"}]}'

LECTURE MAPPING: Ed Donner "AI Engineer Production Track", Week 4 (Multi-Agent / Observability / AgentCore).
  L89 = Multi-agent vs single-agent (planner + workers vs single-agent-with-loop). Orchestrator framing.
        Start-simple golden rule + "experiment, measure metric" — yeh lab ka WHY-split section.
  L90 = ALEX (financial planner SaaS) multi-agent setup: 1 planner + workers, har ek alag Lambda,
        Aurora Serverless v2 DB, "don't anthropomorphize — yeh LLM calls hain, CONTEXT matter karta hai".
  L95 = Context engineering (Schmid/Karpathy): right info+tools, right format, right time. Per-agent
        scoped context = is lab ka dil. "framework matter nahi karta — context ki quality matter karti."
  L96 = Bedrock models + enterprise APIs (LiteLLM `bedrock/<id>` + AWS_REGION_NAME). Prod model path.
  L97 = Agent dir structure (lambda_handler/agent/templates) + homework: kaun tools, kaun structured outputs.
  L98 = Code review: tagger = structured outputs (`output_type=PydanticModel`), reporter = tool,
        planner = orchestrate via @function_tool. Over-engineering trap (Claude Code horror stories).
  NOTE: Lecture ke ALEX agents (planner/tagger/reporter/charter/retirement) vs is lab ke 4 agents
  (planner/analyst/risk/synthesizer) — naam alag, CONCEPT identical: ek orchestrator + scoped workers +
  typed handoffs. Hum role-set ko rebalancing-recommendation ke around tight rakhte taaki ek hi file me
  poora multi-agent loop end-to-end runnable rahe (planner -> analyst+risk parallel-ish -> synth).

DEPLOY RUNBOOK (real cloud, jab key/AWS ho): har agent (`run_*_agent`) ek alag Lambda banta — apna
  `lambda_handler(event, context)` (niche mock-event self-demo dikhaya), package_docker.py se Lambda-Linux
  zip, Bedrock via LiteLLM (`bedrock/<model-id>`, `AWS_REGION_NAME`). Planner ko frontend -> API Gateway
  -> backend Lambda -> SQS queue se request milti (async decouple, L90). Profile/holdings Aurora Serverless
  v2 me (RDS Data API), har agent ka call Langfuse me trace hota (LLM-as-a-judge eval, L111/L112).

COST: Is lab ko LOCALLY chalana = $0 (no LLM call without key, no boto3, no langfuse, no network — pure
  pydantic + sqlite3 + stdlib). LLM key ho to groq free-tier (llama-3.3-70b) 4 chhote calls -> ~$0. REAL
  ALEX deploy (runbook): 5 Lambdas (per-invoke + per-ms, mostly free-tier), Aurora Serverless v2 (idle par
  scale-down, ~paise/hr min ACU), Bedrock per-token (Nova Micro/Lite sasta), Langfuse cloud free-tier ya
  self-host. Ed ka pura capstone estimate chhota — mostly free-tier ke andar jab tum sone se pehle band karo.
"""

import json
import os
import sys
import time
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

# .env load — override=True => .env value shell ki purani value ko jeet jaaye (Ed convention).
# GROQ_API_KEY / DB_CLUSTER_ARN / LANGFUSE_* etc. yahin se uthega.
load_dotenv(override=True)

# pydantic hamare env me guaranteed hai (pyproject). Typed agent outputs + reliable handoff isi par.
from pydantic import BaseModel, Field  # noqa: E402  (load_dotenv ke baad — Ed style)


# ===========================================================================
# get_client — agents ke LLM call ke liye. EXACT helper (placeholder fix ke saath).
# ===========================================================================
# Groq/Gemini OpenAI-compatible hain — sirf base_url alag. Prod ALEX me yeh Bedrock-via-LiteLLM
# (`bedrock/<model-id>`) hota (L96/L98); yahan groq free-tier se same chat.completions shape.
def get_client(provider: str = "groq"):
    """(client, model). Default groq => free. NOTE `or "placeholder"`: OpenAI() None key par
    CONSTRUCTION time hi crash karta hai, isliye placeholder."""
    if provider == "groq":
        return OpenAI(base_url="https://api.groq.com/openai/v1",
                      api_key=os.getenv("GROQ_API_KEY") or "placeholder"), "llama-3.3-70b-versatile"
    if provider == "gemini":
        return OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                      api_key=os.getenv("GOOGLE_API_KEY") or "placeholder"), "gemini-2.5-flash"
    raise ValueError(f"Unknown provider: {provider}")


# ===========================================================================
# ############  PYDANTIC MODELS — typed agent I/O (L97/L98 structured outputs)  ##
# ===========================================================================
# WHY pydantic (na ki dict / free text): agent-to-agent HANDOFF reliable banane ke liye. Synthesizer
# ko Analyst ka `top_holding_pct` ek FLOAT chahiye, ek English paragraph se regex se nikaalna nahi.
# Yeh exactly tagger ka `output_type=InstrumentClassification` (L98) ka spirit hai — LLM ko ek JSON
# schema follow karne par force karo, phir typed object me validate karo. Typed = production trust.

class Holding(BaseModel):
    """User portfolio ka ek instrument. ALEX me yeh Aurora `Position`+`Instrument` se aata (L95 schema)."""
    ticker: str
    value: float                      # USD market value
    asset_class: str = "equity"       # equity / fixed_income / cash / commodity / crypto


class FinancialProfile(BaseModel):
    """Poora user input — yeh ALEX SaaS ka 'user ne brokerage details daale' wala payload (L90)."""
    name: str
    age: int
    risk_tolerance: str = "moderate"  # conservative / moderate / aggressive
    goal: str = "long-term growth with managed risk"
    annual_income: float = 0.0
    holdings: list[Holding] = Field(default_factory=list)

    def total_value(self) -> float:
        return float(sum(h.value for h in self.holdings))


# --- Agent OUTPUT models (har agent ek typed result deta hai) ----------------

class PlanStep(BaseModel):
    """Planner ke break-down ka ek sub-task. WHY id+owner: orchestrator ko routing ke liye chahiye."""
    id: str                            # e.g. "analyze_allocation"
    owner: str                         # kaunsa worker: "analyst" / "risk"
    description: str                   # plain-language sub-task


class PlannerOutput(BaseModel):
    """PlannerAgent ka typed result: goal ko sub-tasks me toda + ek focus-note. (L89 planner role.)"""
    summary: str                       # 1-line restatement of user goal
    steps: list[PlanStep]
    focus_note: str                    # kis cheez par dhyaan dena hai (e.g. "concentration check")


class AllocationSlice(BaseModel):
    """Ek asset-class ka allocation % — analyst ka core numeric output (charter/synth dono use karte)."""
    asset_class: str
    pct: float                         # 0..100


class AnalystOutput(BaseModel):
    """PortfolioAnalystAgent ka typed result: allocation breakdown + diversification read."""
    total_value: float
    allocation: list[AllocationSlice]
    top_holding_ticker: str
    top_holding_pct: float             # single largest position as % of portfolio (concentration signal)
    diversification_comment: str


class RiskFlag(BaseModel):
    """Ek red-flag — severity se synth prioritize karta. (Ed: concentration risk = ALEX ka core feature.)"""
    severity: str                      # "low" / "medium" / "high"
    flag: str                          # e.g. "Single stock > 25% of portfolio"
    rationale: str


class RiskOutput(BaseModel):
    """RiskAgent ka typed result: overall risk + red flags list."""
    overall_risk: str                  # "low" / "moderate" / "high"
    flags: list[RiskFlag]
    suitability_note: str              # risk_tolerance ke against fit


class Recommendation(BaseModel):
    """Synth ka ek actionable rebalancing step. WHY typed: frontend/API ise table me render kar sake."""
    action: str                        # "trim" / "add" / "hold" / "diversify"
    target: str                        # ticker ya asset_class
    detail: str


class SynthOutput(BaseModel):
    """SynthesizerAgent ka FINAL typed result — yahi ALEX SaaS user ko dikhata hai."""
    headline: str
    recommendations: list[Recommendation]
    summary: str


# ===========================================================================
# ############  OBSERVABILITY — Langfuse lazy, warna local JSON span logger  ###
# ===========================================================================
# Week 4 ka Day-4 enterprise piece: har agent (LLM call) ko TRACE karo (L111/L112). Real path = langfuse
# (lazy import jab LANGFUSE_PUBLIC_KEY set). Is env me langfuse/network nahi -> ek LOCAL span logger jo
# structured JSON spans print karta hai (no network). Yeh "trace har agent-to-agent handoff" ka offline
# analog hai — production me yahi spans Langfuse/CloudWatch me jaate, jahaan tum latency/cost/quality dekhte.

class Tracer:
    """Minimal observability shim. `span(name)` ek context-manager deta jo start/stop + metadata JSON
    print karta. Real ALEX me yeh langfuse.trace/span ke peeche hota (LLM-as-a-judge eval bhi yahin)."""

    def __init__(self):
        # LAZY availability check — module top par langfuse import NAHI (missing ho to crash na ho).
        self.backend = "local-json"
        if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
            try:
                from langfuse import Langfuse  # noqa: F401  (lazy on purpose)
                # Real path (reference only — is env me pahunchega hi nahi, koi network nahi karte):
                #   self._lf = Langfuse()  # keys env se; har span -> self._lf.span(...)
                self.backend = "langfuse"
            except Exception as e:
                print(f"[OBS] langfuse import/keys issue ({type(e).__name__}) -> local-json span logger.")
        else:
            print("[OBS] LANGFUSE_* keys nahi mile -> local-json span logger (offline, no network).")

    def span(self, name: str, **meta):
        return _Span(self.backend, name, meta)


class _Span:
    """Ek timed span. with-block ke andar agent chalega; bahar nikalte hi ek JSON line print
    (name, duration_ms, status, meta). Yeh production trace ka offline shape hai."""
    def __init__(self, backend, name, meta):
        self.backend, self.name, self.meta = backend, name, meta
        self.status = "ok"

    def __enter__(self):
        self._t0 = time.time()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.status = f"error:{exc_type.__name__}"  # span me error capture (graceful — re-raise nahi karte ki demo na ruke? niche dekho)
        dur_ms = round((time.time() - self._t0) * 1000, 1)
        rec = {"trace": "alex", "span": self.name, "backend": self.backend,
               "duration_ms": dur_ms, "status": self.status, **self.meta}
        # Structured JSON span line — production me yeh Langfuse/CloudWatch me jaata.
        print(f"[SPAN] {json.dumps(rec)}")
        return False  # exception ko suppress NAHI karte — caller decide kare (hum agents ko safe rakhte hain)


# ===========================================================================
# ############  DATA LAYER — Aurora (lazy boto3 RDS Data API) / sqlite fallback  ##
# ===========================================================================
# L90/L91: ALEX ka data Aurora Serverless v2 me hai (User -> Account -> Position -> Instrument).
# REAL repository = boto3 RDS Data API jab DB_CLUSTER_ARN set + creds. OFFLINE fallback = stdlib sqlite3
# (same `save_profile`/`load_profile` interface) taaki lab locally same code-shape se chale. Hum demo ke
# end me sqlite file _data/ ke andar banate aur CLEANUP karte hain (no leftover).

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_data")


class ProfileRepository:
    """Profile persistence ke do interchangeable backends ke peeche ek interface (L90 decoupling)."""

    def __init__(self):
        self.backend = "sqlite-local"
        self._cluster_arn = os.getenv("DB_CLUSTER_ARN")
        if self._cluster_arn:
            # LAZY boto3 — module top par NAHI. Missing/creds-less ho to sqlite par giro.
            try:
                import boto3  # noqa: F401  (lazy on purpose)
                self.backend = "aurora-data-api"
                # Real path (reference only — is env me pahunchega hi nahi):
                #   self._rds = boto3.client("rds-data")
                #   self._rds.execute_statement(resourceArn=self._cluster_arn, secretArn=..., sql=...)
                print("[DB] DB_CLUSTER_ARN mila + boto3 available -> Aurora RDS Data API path.")
            except ImportError:
                print("[DB] boto3 missing (DB_CLUSTER_ARN set tha) -> sqlite-local fallback (offline, $0).")
        else:
            print("[DB] DB_CLUSTER_ARN nahi mila -> sqlite-local fallback (offline, $0).")

        # sqlite path: ek file _data/alex.db. (Aurora path par yeh file touch nahi hoti.)
        self._db_path = None
        if self.backend == "sqlite-local":
            os.makedirs(_DATA_DIR, exist_ok=True)
            self._db_path = os.path.join(_DATA_DIR, "alex.db")
            self._init_sqlite()

    def _init_sqlite(self):
        import sqlite3  # stdlib — guaranteed available, koi install nahi.
        con = sqlite3.connect(self._db_path)
        # Profile ko ek JSON blob ke roop me store karte (demo ke liye kaafi; prod me normalized tables).
        con.execute("CREATE TABLE IF NOT EXISTS profiles (name TEXT PRIMARY KEY, payload TEXT)")
        con.commit()
        con.close()

    def save_profile(self, profile: FinancialProfile):
        if self.backend == "aurora-data-api":
            # Real: self._rds.execute_statement(... INSERT ...). Yahan reference-only.
            return
        import sqlite3
        con = sqlite3.connect(self._db_path)
        con.execute("INSERT OR REPLACE INTO profiles (name, payload) VALUES (?, ?)",
                    (profile.name, profile.model_dump_json()))
        con.commit()
        con.close()

    def load_profile(self, name: str) -> Optional[FinancialProfile]:
        if self.backend == "aurora-data-api":
            return None  # Real: SELECT payload ... -> FinancialProfile.model_validate_json(...)
        import sqlite3
        con = sqlite3.connect(self._db_path)
        row = con.execute("SELECT payload FROM profiles WHERE name = ?", (name,)).fetchone()
        con.close()
        if not row:
            return None
        return FinancialProfile.model_validate_json(row[0])

    def cleanup(self):
        """Demo ne jo sqlite file banayi usse delete karo — Practical/ me koi leftover na rahe."""
        if self._db_path and os.path.exists(self._db_path):
            os.remove(self._db_path)
        # _data/ khaali ho to wo bhi hata do.
        try:
            if os.path.isdir(_DATA_DIR) and not os.listdir(_DATA_DIR):
                os.rmdir(_DATA_DIR)
        except OSError:
            pass


# ===========================================================================
# ############  LLM HELPER — structured JSON call, graceful no-key  ##########
# ===========================================================================
# Har agent isi ek helper se LLM call karta. response_format=json_object => model ko JSON dene par force
# (L97/L98 structured-output ka provider-agnostic version). Key na ho ya call fail ho to caller apna
# DETERMINISTIC templated stub use karta (har agent ke andar) — exit 0, koi crash/network/cost nahi.

def _llm_json(system_prompt: str, user_prompt: str, max_tokens: int = 500) -> Optional[dict]:
    """LLM se ek JSON object maango. Return dict ya None (key missing / call fail / parse fail).
    None => caller templated stub par girta (graceful degrade)."""
    if not os.getenv("GROQ_API_KEY"):
        return None  # no key => live call hi mat karo (na network, na cost)

    client, model = get_client("groq")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},  # structured output ko force
            max_tokens=max_tokens,
            temperature=0.0,                            # financial advice => deterministic, low creativity
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        # Network/quota/auth/parse fail => crash mat karo, None do (caller stub par giregaa).
        print(f"[LLM] live call fail ({type(e).__name__}: {e}) -> templated stub fallback.")
        return None


# ===========================================================================
# ############  THE 4 AGENTS — har ek = focused-role LLM call -> typed output  ##
# ===========================================================================
# Dhyaan (L90 'don't anthropomorphize'): yeh "team members" nahi hain — yeh 4 LLM CALLS hain, har ek ko
# alag CONTEXT + role-prompt diya gaya. Naam (Planner/Analyst/Risk/Synth) sirf scoped-task ka label hai.
# CONTEXT ENGINEERING (L95): neeche dekho har agent ko KYA context milta hai aur KYUN (zyada nahi, kam nahi).


def run_planner_agent(profile: FinancialProfile, tracer: Tracer) -> PlannerOutput:
    """PlannerAgent (orchestrator brain, L89): goal ko sub-tasks me todta hai aur focus set karta.
    CONTEXT (scoped): sirf goal + risk_tolerance + ek LIGHT profile summary (kitne holdings, total value).
    WHY itna kam: planner ko allocation MATH nahi karni — bas DECIDE karna hai kya analyze hona chahiye.
    Yeh context-engineering hai: planner ko full holdings dena uska kaam dilute karta (over-context)."""
    n = len(profile.holdings)
    light_summary = (f"{profile.name}, age {profile.age}, risk_tolerance={profile.risk_tolerance}, "
                     f"{n} holdings, total ${profile.total_value():,.0f}, goal: {profile.goal}")

    system = ("You are the PLANNER agent in a multi-agent financial planning system named ALEX. "
              "Break the user's goal into analysis sub-tasks for two worker agents: 'analyst' "
              "(computes allocation + diversification) and 'risk' (finds risk red-flags). "
              "Respond ONLY as JSON matching: "
              '{"summary": str, "steps": [{"id": str, "owner": "analyst"|"risk", "description": str}], '
              '"focus_note": str}')
    user = f"USER PROFILE SUMMARY:\n{light_summary}\n\nProduce the plan as JSON."

    with tracer.span("planner", owner="planner", profile=profile.name):
        data = _llm_json(system, user, max_tokens=400)
        if data is not None:
            try:
                return PlannerOutput.model_validate(data)
            except Exception as e:
                print(f"[planner] JSON validate fail ({e}) -> templated stub.")
        # --- DETERMINISTIC TEMPLATED STUB (no-key / fail) — typed output, SAME shape ---
        return PlannerOutput(
            summary=f"Plan for {profile.name}: assess allocation and risk for '{profile.goal}'.",
            steps=[
                PlanStep(id="analyze_allocation", owner="analyst",
                         description="Compute asset-class allocation and identify the largest position."),
                PlanStep(id="assess_risk", owner="risk",
                         description="Flag concentration and suitability risks vs risk_tolerance."),
            ],
            focus_note="Check single-name concentration; verify allocation fits risk_tolerance.",
        )


def run_portfolio_analyst_agent(profile: FinancialProfile, plan: PlannerOutput,
                                tracer: Tracer) -> AnalystOutput:
    """PortfolioAnalystAgent: holdings/allocation analyze karta. CONTEXT (scoped): FULL holdings +
    planner ke ANALYST steps. WHY full holdings yahan (par planner ko nahi): analyst ka actual kaam
    numbers crunch karna hai -> usse pura data chahiye. Yeh hi 'right info at the right time' (L95).
    NOTE: hum allocation/top-holding ko CODE me bhi compute karte (deterministic ground-truth) taaki
    stub bhi REAL numbers de — LLM ko bhi yahi numbers context me dete (hallucination kam, L98 spirit)."""
    total = profile.total_value()
    # Deterministic allocation (asset_class -> sum) — yeh tool-style computation hai (L98 reporter tool).
    by_class: dict[str, float] = {}
    for h in profile.holdings:
        by_class[h.asset_class] = by_class.get(h.asset_class, 0.0) + h.value
    allocation = [AllocationSlice(asset_class=k, pct=round(100 * v / total, 1) if total else 0.0)
                  for k, v in sorted(by_class.items(), key=lambda kv: -kv[1])]
    # Largest single position (concentration ka core signal — ALEX ka headline feature, L90).
    top = max(profile.holdings, key=lambda h: h.value) if profile.holdings else None
    top_ticker = top.ticker if top else "N/A"
    top_pct = round(100 * top.value / total, 1) if (top and total) else 0.0

    analyst_steps = [s.description for s in plan.steps if s.owner == "analyst"]
    facts = {"total_value": total,
             "allocation": [s.model_dump() for s in allocation],
             "top_holding": {"ticker": top_ticker, "pct": top_pct}}

    system = ("You are the PORTFOLIO ANALYST agent in ALEX. Using the PRECOMPUTED facts, write a "
              "diversification_comment. Do NOT change the numbers. Respond ONLY as JSON matching: "
              '{"diversification_comment": str}')
    user = (f"ANALYST SUB-TASKS: {analyst_steps}\n"
            f"PRECOMPUTED FACTS (authoritative, do not alter):\n{json.dumps(facts)}\n\n"
            "Return JSON with diversification_comment only.")

    with tracer.span("analyst", owner="analyst", holdings=len(profile.holdings)):
        comment = None
        data = _llm_json(system, user, max_tokens=250)
        if data is not None and isinstance(data.get("diversification_comment"), str):
            comment = data["diversification_comment"]
        if comment is None:
            # --- TEMPLATED STUB: numbers se ek deterministic comment compose karo ---
            classes = len(by_class)
            comment = (f"Portfolio spans {classes} asset class(es); largest single position "
                       f"{top_ticker} is {top_pct:.1f}% of ${total:,.0f}. "
                       + ("High single-name concentration." if top_pct >= 25
                          else "Concentration within a typical range."))
        return AnalystOutput(total_value=total, allocation=allocation,
                             top_holding_ticker=top_ticker, top_holding_pct=top_pct,
                             diversification_comment=comment)


def run_risk_agent(profile: FinancialProfile, analyst: AnalystOutput, tracer: Tracer) -> RiskOutput:
    """RiskAgent: risk + red flags. CONTEXT (scoped): profile risk_tolerance + ANALYST ka STRUCTURED
    output (allocation + top_holding_pct). WHY typed handoff yahan critical: risk ko analyst ka
    `top_holding_pct` ek FLOAT chahiye threshold compare ke liye — ek paragraph parse karna bug-prone.
    Yeh agent-to-agent handoff hi multi-agent reliability ka dil hai (L98)."""
    flags: list[RiskFlag] = []
    # Deterministic rules (ground-truth red-flags) — stub aur LLM dono ke liye anchor.
    if analyst.top_holding_pct >= 25:
        flags.append(RiskFlag(severity="high",
                              flag=f"{analyst.top_holding_ticker} is {analyst.top_holding_pct:.1f}% of portfolio",
                              rationale="Single-name concentration above 25% raises idiosyncratic risk."))
    equity_pct = next((s.pct for s in analyst.allocation if s.asset_class == "equity"), 0.0)
    if profile.risk_tolerance == "conservative" and equity_pct >= 70:
        flags.append(RiskFlag(severity="medium",
                              flag=f"Equity {equity_pct:.1f}% with conservative risk_tolerance",
                              rationale="Equity weight high relative to stated conservative tolerance."))
    cash_pct = next((s.pct for s in analyst.allocation if s.asset_class == "cash"), 0.0)
    if cash_pct >= 40:
        flags.append(RiskFlag(severity="low",
                              flag=f"Cash drag: {cash_pct:.1f}% in cash",
                              rationale="Large cash balance may underperform goal over the long term."))

    overall = "high" if any(f.severity == "high" for f in flags) else (
        "moderate" if flags else "low")
    context = {"risk_tolerance": profile.risk_tolerance,
               "allocation": [s.model_dump() for s in analyst.allocation],
               "top_holding_pct": analyst.top_holding_pct,
               "detected_flags": [f.model_dump() for f in flags]}

    system = ("You are the RISK agent in ALEX. Given the structured analysis, write a one-sentence "
              "suitability_note about fit vs the user's risk_tolerance. Respond ONLY as JSON matching: "
              '{"suitability_note": str}')
    user = f"STRUCTURED ANALYSIS:\n{json.dumps(context)}\n\nReturn JSON with suitability_note only."

    with tracer.span("risk", owner="risk", flags=len(flags), overall=overall):
        note = None
        data = _llm_json(system, user, max_tokens=200)
        if data is not None and isinstance(data.get("suitability_note"), str):
            note = data["suitability_note"]
        if note is None:
            note = (f"Overall risk is {overall} for a {profile.risk_tolerance} investor; "
                    f"{len(flags)} flag(s) detected.")
        return RiskOutput(overall_risk=overall, flags=flags, suitability_note=note)


def run_synthesizer_agent(profile: FinancialProfile, plan: PlannerOutput, analyst: AnalystOutput,
                          risk: RiskOutput, tracer: Tracer) -> SynthOutput:
    """SynthesizerAgent: sab upstream STRUCTURED outputs ko merge karke FINAL rebalancing recommendation.
    CONTEXT (scoped): plan focus + analyst allocation/concentration + risk flags. WHY synth alag agent:
    iska kaam JUDGEMENT (merge + prioritize) hai, na ki computation — alag role-prompt isse focused
    rakhta. Final output = ALEX SaaS user ko jo dikhta hai (typed -> frontend table me render hota)."""
    # Deterministic recommendations (ground-truth) — high-severity flags se actions derive karo.
    recs: list[Recommendation] = []
    for f in risk.flags:
        if f.severity == "high" and "concentration" in f.rationale.lower():
            recs.append(Recommendation(action="trim", target=analyst.top_holding_ticker,
                                       detail=f"Reduce {analyst.top_holding_ticker} from "
                                              f"{analyst.top_holding_pct:.1f}% toward <20% to cut concentration risk."))
        elif "cash drag" in f.flag.lower():
            recs.append(Recommendation(action="add", target="diversified equity/bond funds",
                                       detail="Deploy excess cash into a diversified mix aligned to the goal."))
        elif "equity" in f.flag.lower():
            recs.append(Recommendation(action="diversify", target="fixed_income",
                                       detail="Shift some equity to fixed income to match conservative tolerance."))
    if not recs:
        recs.append(Recommendation(action="hold", target="portfolio",
                                   detail="Allocation broadly fits the goal; rebalance at next review."))

    upstream = {"focus_note": plan.focus_note,
                "allocation": [s.model_dump() for s in analyst.allocation],
                "top_holding": {"ticker": analyst.top_holding_ticker, "pct": analyst.top_holding_pct},
                "overall_risk": risk.overall_risk,
                "flags": [f.model_dump() for f in risk.flags],
                "draft_recommendations": [r.model_dump() for r in recs]}

    system = ("You are the SYNTHESIZER agent in ALEX. Merge the upstream analysis into a final "
              "rebalancing recommendation. Keep the draft_recommendations as-is in spirit; write a "
              "punchy headline and a 2-sentence summary. Respond ONLY as JSON matching: "
              '{"headline": str, "summary": str}')
    user = f"UPSTREAM (planner+analyst+risk):\n{json.dumps(upstream)}\n\nReturn JSON: headline + summary."

    with tracer.span("synthesizer", owner="synthesizer", recs=len(recs)):
        headline, summary = None, None
        data = _llm_json(system, user, max_tokens=300)
        if data is not None:
            headline = data.get("headline") if isinstance(data.get("headline"), str) else None
            summary = data.get("summary") if isinstance(data.get("summary"), str) else None
        if headline is None:
            headline = f"Rebalancing plan for {profile.name}: risk is {risk.overall_risk}."
        if summary is None:
            summary = (f"Largest position {analyst.top_holding_ticker} at "
                       f"{analyst.top_holding_pct:.1f}% drives a {risk.overall_risk} risk read. "
                       f"Apply {len(recs)} action(s) to align with '{profile.goal}'.")
        return SynthOutput(headline=headline, recommendations=recs, summary=summary)


# ===========================================================================
# ############  ORCHESTRATOR — planner -> analyst+risk -> synthesizer  #######
# ===========================================================================
# Yeh wo "code path" hai jo agents ko WORKFLOW me chalata (L89: ek multi-agent system jisme planner ke
# baad workers, phir synth). NOTE: yeh ek WORKFLOW (code controls order) + multi-agent (specialized roles)
# ka mix hai — Ed kehta hai reality aksar beech me hoti hai. Har step ka STRUCTURED output (typed object)
# agle ko HANDOFF hota (context engineering). analyst+risk ko hum sequentially chalate par dono ek hi
# "stage" hain (planner ke baad, synth ke pehle) — prod me yeh Lambdas parallel invoke ho sakte (SQS/fan-out).

def run_alex(profile: FinancialProfile, repo: ProfileRepository, tracer: Tracer, verbose: bool = True):
    """ALEX multi-agent run. Return ek dict with har agent ka typed output + final recommendation.
    NA crash, NA hang, NA network (no key par sab templated). Yeh ek FastAPI/Lambda route ke peeche
    jaata prod me (planner Lambda jo workers ko invoke karta, L90)."""

    # --- 0) PERSIST profile (Aurora/sqlite) — ALEX SaaS me user ka data store hota ---
    repo.save_profile(profile)
    loaded = repo.load_profile(profile.name)  # round-trip (sqlite path par); demonstrates repo interface
    if loaded is not None:
        profile = loaded  # use the persisted copy (prod: jobs table se uthata, L95)

    if verbose:
        print("-" * 76)
        print(f"USER: {profile.name}, age {profile.age}, risk={profile.risk_tolerance}, "
              f"total ${profile.total_value():,.0f}, holdings={len(profile.holdings)}")
        print(f"GOAL: {profile.goal}")
        print(f"(data backend = {repo.backend}, obs backend = {tracer.backend})")
        print("-" * 76)

    # --- 1) PLANNER (orchestrator brain) -> typed plan ---------------------
    plan = run_planner_agent(profile, tracer)
    if verbose:
        print("\n[1] PLANNER  (goal -> sub-tasks; scoped context = light summary only)")
        print(f"    summary    : {plan.summary}")
        for s in plan.steps:
            print(f"    step       : [{s.owner}] {s.id} -> {s.description}")
        print(f"    focus_note : {plan.focus_note}")

    # --- 2) STAGE-2 workers: ANALYST + RISK (planner ka output handoff) ----
    # Context engineering: analyst ko FULL holdings + analyst-steps; risk ko analyst ka STRUCTURED output.
    analyst = run_portfolio_analyst_agent(profile, plan, tracer)
    if verbose:
        print("\n[2a] PORTFOLIO ANALYST  (full holdings -> allocation + concentration)")
        for a in analyst.allocation:
            print(f"     alloc      : {a.asset_class:<12} {a.pct:5.1f}%")
        print(f"     top holding: {analyst.top_holding_ticker} = {analyst.top_holding_pct:.1f}% (concentration signal)")
        print(f"     comment    : {analyst.diversification_comment}")

    risk = run_risk_agent(profile, analyst, tracer)  # <- typed handoff: analyst -> risk
    if verbose:
        print("\n[2b] RISK  (analyst output handoff -> red flags + suitability)")
        print(f"     overall    : {risk.overall_risk}")
        for f in risk.flags:
            print(f"     flag       : [{f.severity}] {f.flag}")
            print(f"                  -> {f.rationale}")
        print(f"     suitability: {risk.suitability_note}")

    # --- 3) SYNTHESIZER (sab outputs merge -> final recommendation) --------
    final = run_synthesizer_agent(profile, plan, analyst, risk, tracer)
    if verbose:
        print("\n[3] SYNTHESIZER  (merge planner+analyst+risk -> FINAL rebalancing recommendation)")
        print(f"    HEADLINE   : {final.headline}")
        for r in final.recommendations:
            print(f"    rec        : [{r.action}] {r.target} -> {r.detail}")
        print(f"    summary    : {final.summary}")

    return {"plan": plan, "analyst": analyst, "risk": risk, "final": final}


# ===========================================================================
# LAMBDA HANDLER — prod me planner ek Lambda hota (L90/L97). Mock-event self-demo niche.
# ===========================================================================
# Real ALEX me yeh handler SQS se ek job event uthata, Aurora se profile load karta, run_alex chalata,
# result wapas Aurora/jobs-table me likhta (L90). Yahan offline: event se profile parse + run + JSON return.
def lambda_handler(event, context=None):
    """AWS Lambda entrypoint shape (L97). event = {"profile": {...}} ya {"name": ...}.
    Offline test ke liye seedha call kiya ja sakta hai (mock event)."""
    profile_data = event.get("profile") if isinstance(event, dict) else None
    if profile_data is None:
        profile = _sample_profile()
    else:
        profile = FinancialProfile.model_validate(profile_data)
    repo = ProfileRepository()
    tracer = Tracer()
    try:
        out = run_alex(profile, repo, tracer, verbose=False)
        # Lambda me hum typed objects ko JSON-serializable dict me badalte (API response).
        return {"statusCode": 200,
                "body": json.dumps({k: v.model_dump() for k, v in out.items()})}
    finally:
        repo.cleanup()  # demo ki sqlite file clean (Lambda me Aurora hota, koi local file nahi)


# ===========================================================================
# SAMPLE PROFILE — baked-in offline input (L94 ka 'test data' analog). Concentration ON PURPOSE.
# ===========================================================================
def _sample_profile() -> FinancialProfile:
    """Ek realistic profile jisme AAPL deliberately bahut bada hai -> concentration red-flag trigger ho
    (ALEX ka headline feature, L90). Cash bhi thoda zyada -> ek second flag. Risk_tolerance moderate."""
    return FinancialProfile(
        name="Asha Mehta",
        age=38,
        risk_tolerance="moderate",
        goal="retire by 60 with steady growth, manage downside",
        annual_income=120000,
        holdings=[
            Holding(ticker="AAPL", value=90000, asset_class="equity"),    # ~36% -> concentration flag
            Holding(ticker="VOO", value=40000, asset_class="equity"),     # S&P500 ETF
            Holding(ticker="BND", value=30000, asset_class="fixed_income"),
            Holding(ticker="CASH", value=30000, asset_class="cash"),      # ~12% cash
            Holding(ticker="GLD", value=10000, asset_class="commodity"),
        ],
    )


# ===========================================================================
# SELF-DEMO — `uv run <file>` (no args) yahan. No key / no boto3 / no langfuse / no AWS => exit 0.
# ===========================================================================
def run_self_demo():
    print("\n" + "#" * 76)
    print("#  LAB 1 SELF-DEMO — ALEX multi-agent financial planner (CAPSTONE CORE)")
    print("#  planner -> (analyst + risk) -> synthesizer | typed handoffs | graceful offline")
    print("#" * 76 + "\n")

    # --- Teaching: multi-agent vs single-agent (L89) -----------------------
    print("=" * 76)
    print("MULTI-AGENT vs SINGLE-AGENT  (L89)")
    print("=" * 76)
    print("- Single-agent-with-loop (Claude Code): ek LLM + lambi prompt, khud ko loop me call karta.")
    print("- Multi-agent (ALEX): ek PLANNER + scoped WORKERS, har ek apna role-prompt + context.")
    print("- Role split KAB help karta: jab ek sub-task (e.g. risk) ko alag se measure+improve karna ho,")
    print("  ya decoupled build/test/evaluate chahiye (L90). Golden rule: START SIMPLE, phir break-out.")
    print("- 'Don't anthropomorphize' (L90): yeh team-members nahi, 4 LLM CALLS hain — CONTEXT matter karta.")
    print()

    # --- Setup: data repo + tracer (lazy backends -> offline fallbacks) ----
    print("=" * 76)
    print("SETUP  (Aurora->sqlite fallback, Langfuse->local-json fallback — both offline, $0)")
    print("=" * 76)
    repo = ProfileRepository()
    tracer = Tracer()
    print()

    try:
        # --- The capstone run on the baked-in sample profile ---------------
        profile = _sample_profile()
        print("=" * 76)
        print("ALEX RUN  (baked-in sample profile — concentration on purpose)")
        print("=" * 76)
        run_alex(profile, repo, tracer, verbose=True)
        print()

        # --- Teaching: context engineering recap (L95) ---------------------
        print("=" * 76)
        print("CONTEXT ENGINEERING  (L95 — right info, right format, right time)")
        print("=" * 76)
        print("- PLANNER  context = goal + LIGHT summary only (decide kya analyze ho; full data se dilute).")
        print("- ANALYST  context = FULL holdings + analyst-steps (numbers crunch karna hai -> pura data).")
        print("- RISK     context = analyst ka STRUCTURED output (top_holding_pct = float, threshold compare).")
        print("- SYNTH    context = sab upstream typed outputs (merge + prioritize -> final recommendation).")
        print("- TYPED handoff (pydantic) = reliable agent-to-agent contract; free-text parse = bug farm (L98).")
        print()

        # --- Teaching: structured outputs + deployable capstone ------------
        print("=" * 76)
        print("STRUCTURED OUTPUTS + DEPLOYABLE SaaS CAPSTONE  (L90/L97/L98)")
        print("=" * 76)
        print("- Har agent ek PYDANTIC model deta (PlannerOutput/AnalystOutput/RiskOutput/SynthOutput).")
        print("  LLM ko response_format=json_object se JSON par force kiya, phir model_validate_json (L98 tagger).")
        print("- Yahi ALEX = deployable subscription product: user brokerage details deta -> rebalancing advice.")
        print("  Prod: 5 Lambdas (Bedrock via LiteLLM, L96), Aurora Serverless v2, Langfuse/CloudWatch traces.")
        print()

        # --- Lambda handler offline smoke (mock event) ---------------------
        print("=" * 76)
        print("LAMBDA HANDLER  (offline mock-event smoke — prod = planner Lambda behind SQS, L90)")
        print("=" * 76)
        resp = lambda_handler({"profile": _sample_profile().model_dump()})
        body = json.loads(resp["body"])
        print(f"    statusCode = {resp['statusCode']}")
        print(f"    final.headline = {body['final']['headline']}")
        print(f"    final.recommendations = {len(body['final']['recommendations'])} action(s)")
        print()

    finally:
        # CLEANUP — demo ne jo sqlite file/_data banaya usse hata do (Practical/ saaf rahe).
        repo.cleanup()

    print("#" * 76)
    print("#  LAB 1 complete. ALEX = planner -> analyst+risk -> synthesizer; typed handoffs;")
    print("#  Aurora/Langfuse lazy with offline fallbacks; no key/AWS bhi exit 0.")
    print("#" * 76 + "\n")
    raise SystemExit(0)


# ===========================================================================
# MAIN — default self-demo; --profile '<json>' => apni profile par ALEX chalao.
# ===========================================================================
if __name__ == "__main__":
    if "--profile" in sys.argv:
        idx = sys.argv.index("--profile")
        raw = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "{}"
        try:
            profile = FinancialProfile.model_validate_json(raw)
        except Exception as e:
            print(f"[ERR] --profile JSON parse/validate fail ({e}); sample profile use kar rahe.")
            profile = _sample_profile()
        repo = ProfileRepository()
        tracer = Tracer()
        try:
            run_alex(profile, repo, tracer, verbose=True)
        finally:
            repo.cleanup()
        raise SystemExit(0)
    else:
        run_self_demo()
