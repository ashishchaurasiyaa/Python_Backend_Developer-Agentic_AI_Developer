"""
LAB 3 — Package + deploy the ALEX multi-agent system to AWS Lambda (IaC)  [WEEK-4 CAPSTONE]
==========================================================================================
Title: ALEX ka PLANNER orchestrator (multi-agent financial advisor ka dimaag) ko ek REAL
       `def handler(event, context)` me wrap karo jo API-Gateway-proxy (POST /plan) ke peeche
       baithe -> agents chalaye -> ek typed recommendation lautaye. Phir lab ko ek REAL zip
       (build/agent_lambda.zip) me package karo, aur Terraform (terraform/) ko regex se scan
       karke exact `terraform init/plan/apply/destroy` commands print karo. Bina kisi key/
       boto3/langfuse/AWS-creds ke bhi pura chalta hai aur EXIT 0 karta hai.

KYA SEEKHENGE (what concepts):
- LAMBDA HANDLER as API: `handler(event, context)` ek API-Gateway-v2 (HTTP API) PROXY event
  leta hai (event["body"] = JSON string, event["requestContext"]["http"]["method"]/path), use
  parse karta hai, planner orchestrator chalata hai, aur ek API-GW proxy RESPONSE deta hai
  ({"statusCode", "headers", "body": json-string}). Yahi shape API Gateway expect karta hai —
  galat shape = API GW 502 (Internal server error). (L100 lambda_handler.py, L105 API Lambda.)
- MULTI-AGENT ORCHESTRATION (L89/L97/L98): planner ek ORCHESTRATOR hai jo specialist agents ko
  (tagger -> reporter -> charter -> retirement) sequence me chalata hai, har ek ka TYPED output
  (pydantic) leta hai, aur unhe ek final `PlanRecommendation` me jodta hai. Ek-ek agent ek tool/
  step hai (L97: "agent call + tools + structured outputs" — bas yahi teen cheezein).
- PACKAGING Python+deps for Lambda (L100/L105 ka core sabak):
    * zip vs container: chhota code+deps -> zip (250MB unzipped cap). Bada/native-heavy -> container image (10GB).
    * DEPS-SIZE GOTCHA: Lambda Amazon LINUX par chalta hai. Mac/Windows par bana native wheel
      (pydantic-core, numpy, psycopg) Lambda par `ImportError`/GLIBC error de sakta. Isliye Ed
      Docker-Linux env me deps build karta (package_docker.py). Hamara offline packager sirf
      PURE-PYTHON lab files zip karta (deps Lambda LAYER/container se aayenge) — taaki yeh demo
      bina Docker/network ke chale, par sabak heavy comments me samjhaya.
- IaC for the agent stack (L100/L105): terraform/ me aws_lambda_function + IAM (rds-data+bedrock+
  logs) + apigatewayv2 (api+integration+route+stage) + CloudWatch log group. Yeh lab us HCL ko
  RUN nahi karta — sirf regex se RESOURCES list karta hai aur EXACT commands print karta hai
  (init/plan/apply/destroy with -var-file=dev.tfvars). IaC = reproducible, version-controlled,
  one-command infra (manual console clicking ki jagah).
- WHEN AI CODE-GEN WORKS vs FAILS (L104 — is week ka philosophical core): LLM boilerplate
  (CRUD, frontend, scaffolding) par EXCELLENT (training data me tons of examples), par NOVEL/
  complex agentic+infra glue (Lambda agents, tool-calling, brand-new SDKs, IAM policies) par
  STRUGGLE karta — over-engineer, hallucinate. SABAK: LLM-likha code (yeh HCL bhi) deploy se
  PEHLE human review + `terraform plan` + tests MUST. Ek galat IAM `Resource="*"` = prod security hole.

KAISE CHALANA (how to run) — CWD = repo root:
    # Default: self-demo (no key / no boto3 / no langfuse / no AWS-creds bhi chalega, EXIT 0)
    uv run Udemy_EdDonner_ProductionTrack/Week4_MultiAgent_Observability_AgentCore/Practical/lab3_package_deploy_agent_lambda.py

    # Sirf zip package banao (build/agent_lambda.zip):
    uv run Udemy_EdDonner_ProductionTrack/Week4_MultiAgent_Observability_AgentCore/Practical/lab3_package_deploy_agent_lambda.py --package

    # Mock POST /plan handler ko invoke karke recommendation dekho:
    uv run Udemy_EdDonner_ProductionTrack/Week4_MultiAgent_Observability_AgentCore/Practical/lab3_package_deploy_agent_lambda.py --invoke

    # Terraform resources list + exact deploy/destroy commands print (terraform RUN nahi hota):
    uv run Udemy_EdDonner_ProductionTrack/Week4_MultiAgent_Observability_AgentCore/Practical/lab3_package_deploy_agent_lambda.py --terraform

LECTURE MAPPING: Ed Donner "AI Engineer Production Track", Week 4 (CAPSTONE: ALEX multi-agent
  financial advisor — production deploy + observability + guardrails + Bedrock AgentCore).
  L97  = Multi-agent architecture: agent = (LLM call + tools + structured outputs). Planner+4 agents.
  L98  = Multi-agent code-review / orchestration architecture (planner orchestrates specialists).
  L100 = Packaging + deploying multi-agent to Lambda: package_docker.py (Docker-Linux zip, NOT a
         container build), terraform 6_agents (SQS + IAM + S3 objects + 5 Lambdas + CloudWatch).
  L101 = E2E testing on Lambda: test_full.py = REAL Lambda call (cloud) vs test_simple.py (local).
  L102 = Frontend (Next.js) for the production agent system.
  L104 = When AI code-gen works (boilerplate) vs fails (novel agentic/infra). Human-review sabak.
  L105 = Deploying AI-generated APIs with Lambda + Terraform: zip -> S3 -> Lambda + API Gateway
         (throttling/CORS) + CloudFront. FastAPI /docs free Swagger. Week1+Week2 convergence.
  L106 = Testing the live multi-agent system (hit the deployed API Gateway URL).

DEPLOY RUNBOOK (real cloud — jab Docker + AWS creds ho):
  1) backend/ me `uv run package_docker.py`  -> Docker-Linux env me deps + code = agent zip (L100).
     (Hamara offline `--package` iska analog hai — par sirf pure-python files, no Docker/network.)
  2) cd terraform && `terraform init` -> `terraform plan -var-file=dev.tfvars` (REVIEW! L104) ->
     `terraform apply -var-file=dev.tfvars` (yes). -> Lambda + IAM + API Gateway + CloudWatch live.
  3) `terraform output plan_url` -> us URL par POST /plan = live multi-agent run (L106 test_full.py).
  4) Code change ke baad: re-package -> `terraform apply` (ya deploy_all_lambdas.py taint+redeploy).
  5) Teardown: `terraform destroy -var-file=dev.tfvars` (sab resources hata do — bill band).

COST: Is lab ko LOCALLY chalana = $0 (sqlite fallback, local trace logger, pure-python zip, koi
  network/Docker/model-download nahi). LLM key ho to groq free-tier — phir bhi ~$0. REAL deploy:
  Lambda pay-per-invoke (free tier 1M req/mo; agent run shayad 100-500ms compute), API Gateway
  HTTP API ~$1/million req, CloudWatch logs paise me, Aurora Serverless v2 ~$0.06/ACU-hr (idle
  scale-to-low), Bedrock per-token (Nova Pro sasta). Idle stack ka base cost ~$0 (serverless);
  Ed ka pura capstone estimate cheap rehta agar destroy karte raho.
"""

import json
import os
import re
import sys
import zipfile
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# .env load. override=True => .env value shell ki purani value ko jeet jaaye (Ed convention).
# GROQ_API_KEY / DB_CLUSTER_ARN / LANGFUSE_* etc. yahin se uthega (agar set ho).
load_dotenv(override=True)

# pydantic hamare env me guaranteed hai (crewai/langchain dependency). Typed agent outputs
# isi se — L97 ka "structured outputs" wala part. (boto3/langfuse NAHI hain -> lazy + fallback.)
from pydantic import BaseModel, Field  # noqa: E402  (load_dotenv ke baad — Ed style)


# ===========================================================================
# get_client — agent LLM ke liye. EXACT helper (placeholder fix ke saath).
# ===========================================================================
# Groq/Gemini OpenAI-compatible hain — sirf base_url alag. REAL deploy me yeh Bedrock
# (LiteLLM via OpenAI Agents SDK, L97) hota; yahan provider-agnostic groq free fallback.
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


# Is file ka apna folder — saare paths ISKE relative (CWD kuch bhi ho, lab kaam kare).
# WHY: lab ko /tmp se bhi chalaya jaa sakta hai; __file__-relative paths robust hote hain.
HERE = Path(__file__).resolve().parent
TF_DIR = HERE / "terraform"            # hamari Terraform files yahan
BUILD_DIR = HERE / "build"             # zip output yahan banega
DATA_DIR = HERE / "_data"              # sqlite db + traces yahan (demo ke baad cleanup)


# ===========================================================================
# ############  STRUCTURED OUTPUTS — pydantic (L97: agent outputs typed)  ####
# ===========================================================================
# Har agent ek defined SHAPE return kare (free text nahi) taaki orchestrator unhe reliably
# jod sake. Yeh "structured outputs" hai — prod me LLM ko force karte ise JSON-schema me
# bolne ko; yahan hum khud pydantic models me build karte (offline) taaki shape dikhe.

class InstrumentTag(BaseModel):
    """Tagger agent ka per-instrument output (L100: Tesla -> North American equity, 98%/2%)."""
    symbol: str
    asset_class: str = Field(description="e.g. 'North American equity', 'bond', 'cash'")
    equity_pct: float = Field(ge=0, le=100)
    cash_pct: float = Field(ge=0, le=100)


class AgentResult(BaseModel):
    """Ek specialist agent ke ek step ka result. orchestrator inhe collect karta hai."""
    agent: str                       # 'tagger' | 'reporter' | 'charter' | 'retirement'
    ok: bool
    summary: str
    detail: dict = Field(default_factory=dict)


class PlanRecommendation(BaseModel):
    """FINAL output — planner orchestrator ka jod. Yahi POST /plan ka response body banega.
    Typed hone se frontend (L102) reliably render kar sakta + API contract stable rehta."""
    user_id: str
    risk_profile: str                # 'conservative' | 'balanced' | 'aggressive'
    headline: str                    # ek line recommendation
    target_allocation: dict          # {"equity": 70, "bond": 20, "cash": 10}
    agent_results: list[AgentResult] # har specialist agent ka trail (auditability)
    notes: str


# ===========================================================================
# ############  AURORA DATA LAYER — RDS Data API (lazy) OR sqlite fallback  ##
# ===========================================================================
# ALEX ka DB = Aurora Serverless v2, accessed via RDS DATA API (boto3, HTTP — no persistent
# connection pool; Lambda-friendly). Is env me boto3 NAHI hai + koi AWS creds nahi. Isliye:
#   REAL path   : boto3 rds-data client (LAZY) jab DB_CLUSTER_ARN set ho + creds ho.
#   OFFLINE path : stdlib sqlite3 (always available) — SAME repository interface ke peeche.
# Caller (planner) ko farak nahi padta kaun chala — yahi "repository pattern" ka point hai.

class PortfolioRepository:
    """Repository interface — planner isi se positions padhta hai. Do implementations,
    ek hi shape. (Repository pattern = data-access ko business-logic se decouple karna.)"""

    def get_positions(self, user_id: str) -> list[dict]:
        raise NotImplementedError


class AuroraDataApiRepository(PortfolioRepository):
    """REAL prod path — Aurora via RDS Data API (boto3 LAZY). Is offline env me kabhi
    actually chalega nahi (boto3 missing); bas dikhata hai REAL call kaisa hota + graceful
    degrade kaise. make_repository() isko try karke fail par sqlite par girta hai."""

    name = "aurora-rds-data"

    def __init__(self, cluster_arn: str, secret_arn: str, db_name: str, region: str | None = None):
        self.cluster_arn = cluster_arn
        self.secret_arn = secret_arn
        self.db_name = db_name
        self.region = region or os.getenv("AWS_REGION", "us-east-1")

    def get_positions(self, user_id: str) -> list[dict]:
        # LAZY import — module top par NAHI. boto3 missing => poori file crash na ho.
        try:
            import boto3  # noqa: F401  (lazy on purpose)
        except ImportError as e:
            raise RuntimeError(
                "boto3 missing => Aurora RDS Data API use nahi ho sakta. "
                f"AWS not configured -> sqlite fallback. (detail: {e})"
            )
        # Yahan REAL call hota (sirf reference — is env me pahunchega hi nahi):
        #   client = boto3.client("rds-data", region_name=self.region)
        #   resp = client.execute_statement(
        #       resourceArn=self.cluster_arn, secretArn=self.secret_arn, database=self.db_name,
        #       sql="SELECT symbol, qty, price FROM positions WHERE user_id = :uid",
        #       parameters=[{"name": "uid", "value": {"stringValue": user_id}}],
        #   )
        #   return [_row_to_dict(r) for r in resp["records"]]
        raise RuntimeError("Aurora RDS Data API call is reference-only in this offline lab.")


class SqliteRepository(PortfolioRepository):
    """OFFLINE fallback — stdlib sqlite3 (always available). SAME interface jaisa Aurora.
    Ek chhota _data/alex_demo.sqlite file banata, seed karta, query karta. Demo ke baad
    cleanup hota hai (ya _data/ me clearly rehta). KOI network, KOI cloud."""

    name = "sqlite-local"

    def __init__(self, db_path: Path):
        import sqlite3  # stdlib — guaranteed
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._seed()

    def _seed(self):
        cur = self._conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                user_id TEXT, symbol TEXT, qty REAL, price REAL
            )
        """)
        # Idempotent: agar pehle se seed hai to dobara mat daalo.
        cur.execute("SELECT COUNT(*) FROM positions WHERE user_id = ?", ("u_demo",))
        if cur.fetchone()[0] == 0:
            # L104 ke test portfolio jaisa (SPY/QQQ/BND/VTI/cash) — ALEX ki dummy positions.
            rows = [
                ("u_demo", "SPY", 50, 540.0),
                ("u_demo", "QQQ", 30, 480.0),
                ("u_demo", "VTI", 40, 270.0),
                ("u_demo", "BND", 100, 72.0),
                ("u_demo", "TSLA", 10, 250.0),
            ]
            cur.executemany("INSERT INTO positions VALUES (?,?,?,?)", rows)
            self._conn.commit()

    def get_positions(self, user_id: str) -> list[dict]:
        cur = self._conn.cursor()
        cur.execute("SELECT symbol, qty, price FROM positions WHERE user_id = ?", (user_id,))
        return [{"symbol": s, "qty": q, "price": p} for (s, q, p) in cur.fetchall()]

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass


def make_repository() -> PortfolioRepository:
    """CONFIG decide karta hai kaun chalega. DB_CLUSTER_ARN set + creds => Aurora try;
    boto3/creds missing ho to clean Hinglish note ke saath sqlite. Default => sqlite (offline, $0)."""
    cluster_arn = os.getenv("DB_CLUSTER_ARN")
    secret_arn = os.getenv("DB_SECRET_ARN")
    if cluster_arn and secret_arn:
        repo = AuroraDataApiRepository(cluster_arn, secret_arn, os.getenv("DB_NAME", "alex"))
        try:
            repo.get_positions("__probe__")     # availability check (boto3 import) -> fail => fallback
            return repo
        except RuntimeError as e:
            print(f"[INFO] {e}")
            print("[INFO] Aurora unavailable => sqlite local repository (offline, $0) par switch.")
    return SqliteRepository(DATA_DIR / "alex_demo.sqlite")


# ===========================================================================
# ############  OBSERVABILITY — Langfuse (lazy) OR local JSON trace logger  ##
# ===========================================================================
# Week-4 ka ek pillar = observability (L111/L112 Langfuse). Is env me langfuse NAHI + koi
# keys nahi. Isliye:
#   REAL path   : `from langfuse import Langfuse` (LAZY) jab LANGFUSE_* keys set ho.
#   OFFLINE path : LocalTracer — structured JSON spans STDOUT par print + _data/traces.jsonl me.
# Dono ka SAME interface (`span(name)` context manager) — agent code change na ho.

class _Span:
    """Ek span (ek operation) — start/end + status. context manager se auto-close."""
    def __init__(self, tracer, name: str):
        self._tracer = tracer
        self.name = name
        self.status = "ok"
        self.meta: dict = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.status = "error"
            self.meta["error"] = f"{exc_type.__name__}: {exc}"
        self._tracer._emit(self)
        return False  # exception ko swallow mat karo (caller handle kare)


class LocalTracer:
    """OFFLINE observability — JSON spans print + _data/traces.jsonl me append. No network.
    Yeh exactly woh shape hai jo Langfuse cloud me dikhata (name + status + meta), bas local."""
    name = "local-json-tracer"

    def __init__(self, trace_file: Path):
        self.trace_file = trace_file
        trace_file.parent.mkdir(parents=True, exist_ok=True)

    def span(self, name: str) -> _Span:
        return _Span(self, name)

    def _emit(self, span: _Span):
        rec = {"span": span.name, "status": span.status, **span.meta}
        line = json.dumps(rec)
        print(f"    [trace] {line}")
        try:
            with self.trace_file.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass  # tracing kabhi business logic ko crash na kare


def make_tracer() -> LocalTracer:
    """LANGFUSE_* keys set ho to REAL Langfuse try (LAZY import); warna LocalTracer."""
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        try:
            from langfuse import Langfuse  # noqa: F401  (lazy on purpose)
            # REAL path (reference): lf = Langfuse(); lf.trace(...)/lf.span(...)
            # Is offline lab me langfuse install hi nahi, isliye ImportError -> LocalTracer.
            print("[INFO] Langfuse keys mile par is offline lab me langfuse package nahi => LocalTracer.")
        except ImportError as e:
            print(f"[INFO] langfuse missing ({e}) => LocalTracer (offline JSON spans).")
    return LocalTracer(DATA_DIR / "traces.jsonl")


# ===========================================================================
# ############  SPECIALIST AGENTS — har ek ek step (L97/L98)  ###############
# ===========================================================================
# Har agent ek chhota function hai jo positions/context leta hai aur ek TYPED result deta hai.
# REAL ALEX me yeh OpenAI Agents SDK + Bedrock (LiteLLM) se LLM call karte; yahan hum
# DETERMINISTIC local logic se compute karte taaki offline chale. (Structured output ka shape
# bilkul wahi — sirf "kaise bhara" alag.) Optional LLM headline ke liye niche graceful call.

def agent_tagger(positions: list[dict], tracer) -> AgentResult:
    """TAGGER — har instrument ko asset-class + equity/cash split deta (L100 ka Tesla example)."""
    with tracer.span("agent.tagger"):
        # Simple heuristic: BND = bond, baaki equity. (Real me LLM/market-data se aata.)
        tags = []
        for p in positions:
            sym = p["symbol"]
            if sym == "BND":
                tags.append(InstrumentTag(symbol=sym, asset_class="bond", equity_pct=2, cash_pct=98))
            else:
                tags.append(InstrumentTag(symbol=sym, asset_class="North American equity",
                                          equity_pct=98, cash_pct=2))
        return AgentResult(agent="tagger", ok=True,
                           summary=f"{len(tags)} instruments tagged",
                           detail={"tags": [t.model_dump() for t in tags]})


def agent_reporter(positions: list[dict], tracer) -> AgentResult:
    """REPORTER — portfolio value + per-position value ka report (L100: 'Report generated')."""
    with tracer.span("agent.reporter"):
        total = sum(p["qty"] * p["price"] for p in positions)
        lines = [{"symbol": p["symbol"], "value": round(p["qty"] * p["price"], 2)} for p in positions]
        return AgentResult(agent="reporter", ok=True,
                           summary=f"portfolio value = ${total:,.2f}",
                           detail={"total": round(total, 2), "positions": lines})


def agent_charter(reporter_detail: dict, tracer) -> AgentResult:
    """CHARTER — allocation breakdown (equity/bond/cash %) jo chart ban sake (L100 charts)."""
    with tracer.span("agent.charter"):
        # Reporter ke values se equity vs bond vs cash % nikaalo (simple bucket).
        total = reporter_detail.get("total", 0) or 1
        bond_val = sum(p["value"] for p in reporter_detail.get("positions", []) if p["symbol"] == "BND")
        equity_val = total - bond_val
        alloc = {"equity": round(equity_val / total * 100), "bond": round(bond_val / total * 100), "cash": 0}
        return AgentResult(agent="charter", ok=True,
                           summary=f"allocation {alloc}",
                           detail={"allocation": alloc})


def agent_retirement(reporter_detail: dict, target_income: float, tracer) -> AgentResult:
    """RETIREMENT — kya portfolio target retirement income support karta (L104 ka 80,000 example).
    4% safe-withdrawal rule se estimate: sustainable_income ~= portfolio * 0.04."""
    with tracer.span("agent.retirement"):
        total = reporter_detail.get("total", 0)
        sustainable = round(total * 0.04, 2)
        on_track = sustainable >= target_income
        return AgentResult(agent="retirement", ok=True,
                           summary=("on track" if on_track else "shortfall")
                                   + f" (sustainable ${sustainable:,.2f} vs target ${target_income:,.2f})",
                           detail={"sustainable_income": sustainable,
                                   "target_income": target_income, "on_track": on_track})


def _llm_headline(rec_context: dict) -> str | None:
    """OPTIONAL — agar GROQ_API_KEY ho to ek one-line headline LLM se. Key na ho => None
    (planner ek deterministic templated headline use karega). Graceful: network/quota fail => None."""
    if not os.getenv("GROQ_API_KEY"):
        return None
    client, model = get_client("groq")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise financial advisor. One short sentence only."},
                {"role": "user", "content": f"Summarize this portfolio plan in one line: {json.dumps(rec_context)}"},
            ],
            max_tokens=60, temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"    [INFO] LLM headline fail ({type(e).__name__}) => templated headline.")
        return None


# ===========================================================================
# ############  PLANNER ORCHESTRATOR — multi-agent ka dimaag (L98)  #########
# ===========================================================================
# Planner specialist agents ko SEQUENCE me chalata hai (tagger -> reporter -> charter ->
# retirement), har ka typed result collect karta, aur ek final PlanRecommendation me jodta.
# Yahi POST /plan ke peeche chalta hai. NA crash, NA network (LLM optional + graceful).
def run_planner(user_id: str, risk_profile: str = "balanced",
                target_income: float = 80_000, repo: PortfolioRepository | None = None,
                tracer: LocalTracer | None = None) -> PlanRecommendation:
    """Multi-agent orchestration. repo/tracer na diye to default (sqlite + LocalTracer)."""
    if repo is None:
        repo = make_repository()
    if tracer is None:
        tracer = make_tracer()

    with tracer.span("planner.orchestrate"):
        # --- positions padho (Aurora ya sqlite — repo ke peeche) ---
        positions = repo.get_positions(user_id)

        # --- specialist agents chalao (sequence; ek ka output agle ko feed) ---
        r_tag = agent_tagger(positions, tracer)
        r_report = agent_reporter(positions, tracer)
        r_chart = agent_charter(r_report.detail, tracer)
        r_retire = agent_retirement(r_report.detail, target_income, tracer)

        alloc = r_chart.detail["allocation"]
        # risk_profile se thoda allocation tilt (deterministic — teaching ke liye saaf).
        if risk_profile == "conservative":
            alloc = {"equity": 40, "bond": 50, "cash": 10}
        elif risk_profile == "aggressive":
            alloc = {"equity": 85, "bond": 10, "cash": 5}

        # --- headline: LLM (optional) ya templated ---
        ctx = {"value": r_report.detail["total"], "allocation": alloc,
               "retirement": r_retire.summary}
        headline = _llm_headline(ctx)
        mode = "live-llm"
        if headline is None:
            mode = "templated"
            headline = (f"Portfolio ${r_report.detail['total']:,.0f} ({risk_profile}); "
                        f"{r_retire.summary}. (templated — GROQ_API_KEY missing tha)")

        return PlanRecommendation(
            user_id=user_id,
            risk_profile=risk_profile,
            headline=headline,
            target_allocation=alloc,
            agent_results=[r_tag, r_report, r_chart, r_retire],
            notes=f"repo={repo.name}, tracer={tracer.name}, headline_mode={mode}. "
                  f"NOT official financial advice (L104 disclaimer).",
        )


# ===========================================================================
# ############  LAMBDA HANDLER — API-Gateway-v2 PROXY (L100/L105)  ##########
# ===========================================================================
# Yeh wahi `def handler(event, context)` hai jo Lambda har invocation par call karta (L100
# lambda_handler.py). API Gateway v2 (HTTP API) PROXY mode me event ka shape:
#   event["requestContext"]["http"]["method"] -> "POST"
#   event["requestContext"]["http"]["path"]   -> "/plan"
#   event["body"]                              -> JSON string (request body)
# Response MUST yeh shape ho warna API GW 502 deta hai:
#   {"statusCode": int, "headers": {...}, "body": "<json string>"}
def _response(status: int, payload: dict) -> dict:
    """API-GW proxy response banane wala helper. body = JSON STRING (dict nahi!) — common
    bug: agar body ko dict chhod do to API GW use ulti-pulti string me bhej deta."""
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"},  # CORS — frontend (L102) ke liye
        "body": json.dumps(payload),
    }


def handler(event, context):  # noqa: ARG001 (context Lambda runtime deta — yahan use nahi)
    """ALEX planner orchestrator ka Lambda entrypoint, API-Gateway-proxy ke peeche.
    POST /plan -> body parse -> run_planner() -> PlanRecommendation -> proxy response.
    Defensive: galat method/path/JSON par clean 4xx (crash nahi) — kyunki internet se kuch
    bhi aa sakta. Yeh exactly woh contract hai jo terraform/main.tf ka apigatewayv2 expect karta."""
    # --- method + path nikaalo (HTTP API v2 shape). Defaults taaki direct-invoke bhi chale. ---
    rc = (event or {}).get("requestContext", {})
    http = rc.get("http", {})
    method = http.get("method", event.get("httpMethod", "POST"))  # v1 fallback bhi
    path = http.get("path", event.get("path", "/plan"))

    # --- routing: sirf POST /plan support (baaki -> 404/405). ---
    if path.rstrip("/") not in ("/plan", ""):
        return _response(404, {"error": "not found", "path": path,
                               "hint": "POST /plan use karo"})
    if method.upper() != "POST":
        return _response(405, {"error": "method not allowed", "method": method,
                               "hint": "POST /plan use karo"})

    # --- body parse (JSON string -> dict). Galat JSON => 400 (crash nahi). ---
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        # API GW kabhi-kabhi body base64 me deta — decode karo (defensive).
        import base64
        try:
            raw = base64.b64decode(raw).decode("utf-8")
        except Exception:
            return _response(400, {"error": "invalid base64 body"})
    try:
        body = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except json.JSONDecodeError as e:
        return _response(400, {"error": "invalid JSON body", "detail": str(e)})

    user_id = body.get("user_id", "u_demo")
    risk_profile = body.get("risk_profile", "balanced")
    target_income = float(body.get("target_income", 80_000))

    # --- orchestrator chalao. Koi bhi unexpected error => 500 (clean, logged). ---
    try:
        rec = run_planner(user_id=user_id, risk_profile=risk_profile,
                          target_income=target_income)
    except Exception as e:
        # Production me yeh CloudWatch me jaata; user ko generic 500 (internals leak na ho).
        print(f"[ERROR] planner failed: {type(e).__name__}: {e}")
        return _response(500, {"error": "internal error", "type": type(e).__name__})

    # pydantic model -> dict -> JSON string (proxy response). 200 OK.
    return _response(200, rec.model_dump())


# ===========================================================================
# ############  PACKAGER — lab(s) ko build/agent_lambda.zip me zip karna  ###
# ===========================================================================
# REAL ALEX: package_docker.py Docker-Linux env me CODE + native DEPS install karke zip banata
# (L100/L105). WHY Docker: Lambda Amazon Linux par chalta — Mac/Windows wheel toot sakta.
# Hamara offline packager sirf PURE-PYTHON lab files zip karta (deps NAHI — woh Lambda layer/
# container se aayenge), taaki yeh demo bina Docker/network ke chale aur sabak comments me rahe.
def build_lambda_zip(verbose: bool = True) -> Path:
    """Lab .py (handler ke saath) ko build/agent_lambda.zip me REAL zip karo. Offline, stdlib
    zipfile. Module name 'agent_lambda.py' rakhte taaki Terraform ka handler='agent_lambda.handler'
    match kare. Returns zip path. (Idempotent: purana zip overwrite — L100 'fresh zip' behaviour.)"""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = BUILD_DIR / "agent_lambda.zip"

    # Lambda handler module ka naam 'agent_lambda.py' hona chahiye (handler='agent_lambda.handler').
    # Hum is lab file ko ZIP ke andar us naam se daalte hain (arcname). Yeh ek common packaging
    # trick — source filename alag, deploy artifact ke andar naam handler-config se match.
    files_to_pack = [(Path(__file__), "agent_lambda.py")]

    if verbose:
        print(f"[package] build dir   : {BUILD_DIR}")
        print(f"[package] zip target  : {zip_path}")
        print("[package] mode        : OFFLINE pure-python (deps NAHI — Lambda layer/container se).")
        print("[package] real path   : package_docker.py Docker-Linux env me code+native-deps build (L100).")

    # ZIP_DEFLATED = compression on (chhota artifact). source_code_hash Terraform isi par.
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for src, arcname in files_to_pack:
            zf.write(src, arcname=arcname)

    size_kb = zip_path.stat().st_size / 1024
    if verbose:
        print(f"[package] wrote       : {zip_path.name}  ({size_kb:.1f} KB, "
              f"{len(files_to_pack)} file(s))")
        # DEPS-SIZE GOTCHA teaching: zip cap 250MB unzipped; native deps bade -> container.
        print("[package] GOTCHA      : Lambda zip cap = 250MB unzipped. pydantic-core/numpy/")
        print("[package]               boto3 add karte hi yeh phool jaata — tab CONTAINER image")
        print("[package]               (10GB cap) ya Lambda LAYER better. Aur deps Amazon-Linux")
        print("[package]               ke liye build karo (Docker), warna Lambda par ImportError.")
    return zip_path


# ===========================================================================
# ############  TERRAFORM SCANNER — regex se resources list (RUN nahi)  #####
# ===========================================================================
# Yeh terraform/main.tf ko PADHTA hai aur `resource "<type>" "<name>"` blocks ko regex se
# nikaalta hai. Terraform RUN NAHI hota (na init, na apply) — sirf static parse + summary.
# WHY regex (na ki real HCL parser): teaching ke liye kaafi + zero-dependency. Production
# audit ke liye `terraform show -json` / hcl2 use karte; yahan intent dikhana hai.
_RESOURCE_RE = re.compile(r'^\s*resource\s+"([^"]+)"\s+"([^"]+)"\s*\{', re.MULTILINE)


def scan_terraform_resources(tf_dir: Path = TF_DIR) -> list[tuple[str, str, str]]:
    """tf_dir ke saare *.tf padho, har `resource "type" "name"` nikaalo.
    Returns list of (resource_type, resource_name, file_name). Koi side-effect nahi."""
    found: list[tuple[str, str, str]] = []
    if not tf_dir.is_dir():
        return found
    for tf_file in sorted(tf_dir.glob("*.tf")):
        text = tf_file.read_text(encoding="utf-8")
        for m in _RESOURCE_RE.finditer(text):
            found.append((m.group(1), m.group(2), tf_file.name))
    return found


def print_terraform_plan(tf_dir: Path = TF_DIR):
    """Parsed resources + EXACT terraform commands print karo (RUN nahi)."""
    print("=" * 74)
    print("TERRAFORM SCAN  (regex parse — terraform RUN nahi hota, sirf list + commands)")
    print("=" * 74)
    resources = scan_terraform_resources(tf_dir)
    if not resources:
        print(f"[WARN] {tf_dir} me koi .tf resource nahi mila (path check karo).")
    else:
        print(f"terraform dir : {tf_dir}")
        print(f"resources     : {len(resources)} (file-by-file niche)")
        # Group readable summary — type ko thoda human-friendly tag bhi.
        friendly = {
            "aws_lambda_function": "Lambda (planner orchestrator — API ka dimaag)",
            "aws_iam_role": "IAM role (Lambda execution identity)",
            "aws_iam_role_policy": "IAM policy (rds-data + bedrock + logs perms)",
            "aws_cloudwatch_log_group": "CloudWatch log group (Lambda logs)",
            "aws_apigatewayv2_api": "API Gateway v2 HTTP API (front-door)",
            "aws_apigatewayv2_integration": "API GW -> Lambda integration (AWS_PROXY)",
            "aws_apigatewayv2_route": "Route (POST /plan)",
            "aws_apigatewayv2_stage": "Stage ($default, auto-deploy, throttling)",
            "aws_lambda_permission": "Lambda permission (API GW ko invoke karne do)",
        }
        for (rtype, rname, fname) in resources:
            tag = friendly.get(rtype, "")
            print(f"  - {rtype}.{rname:<22} [{fname}]  {tag}")

    # --- EXACT commands (copy-paste ready). Yeh RUN nahi hote — sirf print. ---
    print()
    print("EXACT COMMANDS (run karne ke liye — yeh lab inhe RUN nahi karta):")
    # Absolute path dikhao (CWD kuch bhi ho — /tmp se chalao to bhi sahi rahe; relpath
    # ulta-pulta `../../Users/...` de deta jab CWD repo ke bahar ho).
    print(f"  cd {tf_dir}")
    print("  terraform init")
    print("  terraform plan    -var-file=dev.tfvars   # <-- REVIEW karo (L104: LLM-likha HCL!)")
    print("  terraform apply   -var-file=dev.tfvars   # 'yes' confirm -> infra live")
    print("  terraform output  plan_url               # POST URL -> L106 live test")
    print("  terraform destroy -var-file=dev.tfvars   # teardown -> bill band")
    print()
    print("L104 SABAK: yeh HCL ek LLM bhi likh sakta — par deploy se PEHLE `terraform plan`")
    print("           + human review MUST. Ek galat IAM Resource=\"*\" = production security hole.")
    print()


# ===========================================================================
# ############  cleanup — demo ne jo temp banaya wo hata do  #################
# ===========================================================================
def cleanup_demo_artifacts(repo, keep_build: bool = True):
    """sqlite db + traces.jsonl hata do (demo ke baad clean). build zip ko keep_build par
    rakhte hain (Terraform usi ko reference karta — teaching ke liye dikhna chahiye)."""
    if isinstance(repo, SqliteRepository):
        repo.close()
    for p in [DATA_DIR / "alex_demo.sqlite", DATA_DIR / "traces.jsonl"]:
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass
    # _data/ khaali ho gaya to use bhi hata do (clean Practical/ dir).
    try:
        if DATA_DIR.exists() and not any(DATA_DIR.iterdir()):
            DATA_DIR.rmdir()
    except Exception:
        pass


# ===========================================================================
# SELF-DEMO — `uv run <file>` (no args) yahan. No key / no boto3 / no AWS => exit 0.
# ===========================================================================
def run_self_demo():
    print("\n" + "#" * 74)
    print("#  LAB 3 SELF-DEMO — Package + deploy ALEX multi-agent to Lambda (IaC)")
    print("#  (no key / no boto3 / no langfuse / no AWS-creds bhi OK — exit 0)")
    print("#" * 74 + "\n")

    # --- 1) MOCK POST /plan event -> handler() invoke (L101/L106 ka offline analog) -------
    print("=" * 74)
    print("[1] HANDLER  — mock 'POST /plan' API-Gateway-v2 event ko handler() me bhejo")
    print("=" * 74)
    mock_event = {
        # API Gateway v2 (HTTP API) PROXY event ka real shape:
        "requestContext": {"http": {"method": "POST", "path": "/plan"}},
        "headers": {"content-type": "application/json"},
        "body": json.dumps({"user_id": "u_demo", "risk_profile": "balanced",
                            "target_income": 80000}),
        "isBase64Encoded": False,
    }
    print("mock event (API GW v2 proxy shape):")
    print(f"    method={mock_event['requestContext']['http']['method']}  "
          f"path={mock_event['requestContext']['http']['path']}")
    print(f"    body={mock_event['body']}")
    print()
    resp = handler(mock_event, None)   # <-- REAL handler call (offline; sqlite + LocalTracer)
    print(f"\nhandler -> statusCode={resp['statusCode']}")
    rec = json.loads(resp["body"])
    print(f"    headline   : {rec['headline']}")
    print(f"    allocation : {rec['target_allocation']}")
    print(f"    agents     : {[a['agent'] + ('OK' if a['ok'] else 'X') for a in rec['agent_results']]}")
    print(f"    notes      : {rec['notes']}")
    print()

    # Bonus: ek BAD request bhi dikhao (GET) — graceful 405, crash nahi.
    bad = handler({"requestContext": {"http": {"method": "GET", "path": "/plan"}}}, None)
    print(f"[1b] bad request (GET /plan) -> statusCode={bad['statusCode']} "
          f"(graceful, crash nahi): {json.loads(bad['body'])}")
    print()

    # --- 2) PACKAGER -> build/agent_lambda.zip (REAL zip, offline) ------------------------
    print("=" * 74)
    print("[2] PACKAGER — lab ko build/agent_lambda.zip me REAL zip karo (offline, stdlib)")
    print("=" * 74)
    zip_path = build_lambda_zip(verbose=True)
    # Verify zip actually bana + handler module andar hai.
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    print(f"[package] zip contents: {names}  (handler module = agent_lambda.py)")
    print()

    # --- 3) TERRAFORM SCAN — resources list + exact commands (RUN nahi) -------------------
    print_terraform_plan()

    # --- 4) WHEN AI CODE-GEN WORKS vs FAILS (L104) — teaching -----------------------------
    print("=" * 74)
    print("[4] WHEN AI CODE-GEN WORKS vs FAILS  (L104 — is week ka core sabak)")
    print("=" * 74)
    print("  WORKS  (LLM fast)  : boilerplate — CRUD routes, Next.js frontend, scaffolding,")
    print("                       (aur haan, simple Terraform) — training data me tons examples.")
    print("  FAILS  (LLM slow)  : novel agentic glue — Lambda agents, tool-calling, brand-new")
    print("                       SDKs (OpenAI Agents SDK, LiteLLM->Bedrock), IAM policies.")
    print("  ROI (Ed)           : frontend 2 weeks -> 1.5 din (big win); agentic 1 week -> 2 weeks")
    print("                       (net NEGATIVE). Overall ~60% time.")
    print("  RULE               : LLM-likha code (yeh handler + HCL bhi) -> human review +")
    print("                       `terraform plan` + tests, PHIR deploy. Ek galat IAM = prod hole.")
    print()

    # --- 5) DEPLOY RUNBOOK pointer (L100/L105/L106) ---------------------------------------
    print("=" * 74)
    print("[5] DEPLOY RUNBOOK  (real cloud — L100/L105/L106)")
    print("=" * 74)
    print("  1) backend/: uv run package_docker.py  (Docker-Linux: code + native deps -> zip)")
    print("  2) terraform/: init -> plan -var-file=dev.tfvars (REVIEW) -> apply -var-file=dev.tfvars")
    print("  3) terraform output plan_url  ->  POST /plan  (L106 test_full.py = real Lambda call)")
    print("  4) code change -> re-package -> apply (ya deploy_all_lambdas.py taint+redeploy)")
    print("  5) terraform destroy -var-file=dev.tfvars  (teardown — bill band)")
    print()

    # --- cleanup: sqlite/traces hata do; build zip rakho (Terraform reference karta) ------
    # handler ne andar apna repo banaya tha; demo ka cleanup ke liye ek fresh banake close.
    cleanup_demo_artifacts(make_repository(), keep_build=True)
    print("[cleanup] sqlite db + traces.jsonl hataye. build/agent_lambda.zip RAKHA "
          "(Terraform isi ko reference karta).")

    print("\n" + "#" * 74)
    print("#  LAB 3 complete. handler(POST /plan) -> multi-agent orchestration -> typed reco;")
    print("#  packager -> real zip; terraform scan -> resources + exact commands; L104 sabak.")
    print("#  Aurora->sqlite + Langfuse->LocalTracer graceful; no key/AWS/network -> exit 0.")
    print("#" * 74 + "\n")
    raise SystemExit(0)


# ===========================================================================
# MAIN — default self-demo; flags se individual pieces.
# ===========================================================================
if __name__ == "__main__":
    args = sys.argv[1:]
    if "--package" in args:
        build_lambda_zip(verbose=True)
        raise SystemExit(0)
    elif "--invoke" in args:
        # Mock POST /plan -> handler. risk_profile arg se override kar sakte ho.
        risk = "balanced"
        if "--risk" in args:
            i = args.index("--risk")
            if i + 1 < len(args):
                risk = args[i + 1]
        ev = {
            "requestContext": {"http": {"method": "POST", "path": "/plan"}},
            "body": json.dumps({"user_id": "u_demo", "risk_profile": risk, "target_income": 80000}),
            "isBase64Encoded": False,
        }
        out = handler(ev, None)
        print(json.dumps(json.loads(out["body"]), indent=2))
        cleanup_demo_artifacts(make_repository(), keep_build=True)
        raise SystemExit(0)
    elif "--terraform" in args:
        print_terraform_plan()
        raise SystemExit(0)
    else:
        run_self_demo()
