"""
LAB 4 — OBSERVABILITY: tracing (spans) + LLM-as-a-Judge eval  [WEEK 4 CAPSTONE]
================================================================================
Title: Ek multi-agent system ko OBSERVABLE + CONTINUOUSLY-EVALUATED banao. Do cheezein:
       (1) `trace(name)` — ek context-manager/decorator jo SPANS record karta hai
           (name, latency_ms, input/output, metadata). REAL path = LAZY Langfuse client
           (jab LANGFUSE_PUBLIC_KEY/SECRET set ho). OFFLINE fallback = LocalTracer jo
           structured JSON spans PRINT karta hai aur ek nested trace-tree rakhta hai.
       (2) `judge_response(question, answer, criteria)` — LLM-as-a-Judge: ek LLM (get_client)
           se answer ko 1-5 score karwao given criteria par, aur ek pydantic Verdict
           {score, reasoning, pass} return karo. Key na ho => DETERMINISTIC heuristic judge
           (length/keyword based) — phir bhi chalta hai. Judge ko ek AUTOMATED EVAL ki tarah
           kuch sample Q/A pairs par chala ke CloudWatch-style metric (judge_score) emit karte.
       Bina kisi key / langfuse / boto3 / AWS / network ke pura chalta hai aur EXIT 0 karta hai.

KYA SEEKHENGE (what concepts):
- TRACING / SPANS — multi-agent DEBUGGING ka DIL (L111/L112):
    Ek "trace" = ek poora agent operation (jaise planner -> reporter -> judge). Ek "span" =
    us trace ke andar ek named sub-operation (jaise sirf 'judge' wala step). Har span record
    karta hai: kya andar gaya (input), kya bahar aaya (output), kitna time laga (latency_ms),
    aur extra metadata (model, tokens, score). WHY: jab 5 agents parallel chal rahe hon aur
    kuch slow/galat ho, to spans se EXACTLY pata chalta hai KAUN sa step + KITNA time + KYA I/O.
    Yeh backend dev ka distributed-tracing (OpenTelemetry/Jaeger spans) ka LLM-world avatar hai.
- LLM-AS-A-JUDGE — production me AUTOMATED quality eval (L111/L112):
    Ek model se DOOSRE model ka output judge karwana. Insaan har answer manually check nahi kar
    sakta (scale), aur exact-match metrics LLM output par kaam nahi karte (har baar wording alag).
    Isliye ek "judge" LLM ko criteria deke 1-5 score + reasoning maangte hain. WHY production me
    matter karta: (a) regression detection — naya prompt/model deploy karne par quality gir to nahi
    rahi, (b) GUARDRAIL — score < threshold to response BLOCK karke safe fallback bhejo (L112 me
    Ed 0.3 threshold use karta), (c) dashboards/alarms — judge_score ek METRIC ban jaata jis par
    alert laga sakte ho.
- EXPLAINABLE AI — reasoning PEHLE, score BAAD me (L110/L111 ka critical trick):
    LLM token-by-token generate karta hai. Agar pehle score maango phir reasoning, to reasoning
    sirf ek post-hoc "justification" hota hai us score ke liye jo model already de chuka. Isliye
    pydantic Verdict me `reasoning` field `score` se PEHLE declare karte hain (field order =
    generation order) — model ko pehle SOCHNE par force karta, score zyada consistent aata.
- LANGFUSE vs CLOUDWATCH — DO alag observability layers (L109 vs L111/L112):
    * Langfuse = LLM-NATIVE traces: prompts, completions, tokens, agent-to-agent conversations,
      judge scores. "Monitoring on steroids" — system ke INTERNALS ka deep insight (unknown-unknowns).
    * CloudWatch = INFRA metrics: Lambda duration, error rate, invocations, throttles, dashboards
      + ALARMS (threshold -> email/page). Yeh "known knowns" — predefined metrics.
    Dono COMPLEMENT karte hain: Langfuse "kya bola/kya socha", CloudWatch "kitna time/kitne errors".
    NOTE (L112): Bedrock model COST Langfuse tak report nahi hota — cost AWS Cost Explorer me alag.
- GRACEFUL DEGRADE (Weeks 1-3 ki proven convention): har optional cheez LAZY import + try/except.
    langfuse missing/no-key => LocalTracer. LLM key missing => deterministic heuristic judge.
    boto3 missing/no-AWS => CloudWatch put_metric_data ko skip karke ek "[metric]" line print.
    NEVER crash / hang / download. Self-demo har haal me EXIT 0.

KAISE CHALANA (how to run) — CWD = repo root:
    # Default: self-demo (no key / no langfuse / no AWS / no download bhi chalega, exit 0)
    uv run Udemy_EdDonner_ProductionTrack/Week4_MultiAgent_Observability_AgentCore/Practical/lab4_observability_tracing_judge.py

    # Sirf ek answer ko judge karna ho (heuristic ya live, key par depend):
    uv run Udemy_EdDonner_ProductionTrack/Week4_MultiAgent_Observability_AgentCore/Practical/lab4_observability_tracing_judge.py --judge "What is RAG?" "RAG retrieves context then generates a grounded, cited answer."

LECTURE MAPPING: Ed Donner "AI Engineer Production Track", Week 4 · Day 4 (L107-L112).
  L107 = Enterprise-grade AI monitoring/security/observability (overview — 3 pillars: monitoring,
         guardrails, observability). Yeh lab "observability + eval" pillar build karta.
  L109 = CloudWatch dashboards (AI Model Usage: Bedrock/SageMaker invocations/tokens/latency;
         Agent Performance: execution time/errors/throttles). `emit_cloudwatch_metric()` isi se —
         judge_score ko ek custom CloudWatch metric ki tarah emit karte (dashboards/alarms ke liye).
  L110 = Monitoring + guardrails + explainability. "rationale pehle, answer baad me" trick yahin se
         (Verdict.reasoning before .score). tenacity exponential-backoff retry ka mental-model bhi.
  L111 = Advanced LLM observability with Langfuse + the `judge` module seed. `with observe()` wrapper,
         span concept, aur Evaluation{feedback, score} structured-output judge — sab yahin introduce hua.
         Hamara LocalTracer = us `observe` wrapper ka offline analog (Langfuse na ho to local JSON spans).
  L112 = LLM-as-a-Judge pattern wired into reporter's lambda handler: span 'judge', span.score(),
         create_event(), aur GUARDRAIL (score < 0.3 => report block, generic message). Hamara
         `run_eval_suite()` + guardrail check exactly yahi shape hai (offline).

DEPLOY RUNBOOK (real cloud, jab keys/AWS ho): yeh `trace()` ka real path Langfuse client banata
  (langfuse_public_key/secret + host Terraform tfvars se — L111). Agent code `with trace("planner")`
  + `with observe()` me wrap hota; har LLM/tool call ek span. judge_response() reporter ke lambda
  handler me chalta, span.score("judge", value) Langfuse me register hota, score<0.3 par guardrail
  response wipe kar deta (L112). judge_score ko CloudWatch custom metric ki tarah bhi push karte
  (boto3 put_metric_data) taaki "Agent Quality" dashboard + alarm (avg judge_score < 3 => page) bane.

COST: Is lab ko LOCALLY chalana = $0 (LocalTracer + heuristic judge, koi download/network nahi). LLM
  key ho to groq free-tier (llama-3.3-70b) judge chalata — phir bhi ~$0. REAL deploy: Langfuse free
  plan = $0 (L111 me Ed ne explicitly free plan liya); judge ek extra LLM call/run = per-token Bedrock
  Nova (paise-bhar); CloudWatch custom metrics ~$0.30/metric/month + dashboards ~$3/dashboard/month;
  alarms ~$0.10/alarm/month. Ed ka pura Week-4 enterprise layer effectively free-tier ke aas-paas.
"""

import json
import os
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field

from dotenv import load_dotenv
from openai import OpenAI

# .env load. override=True => .env value shell ki purani value ko jeet jaaye (Ed Donner convention).
# GROQ_API_KEY / LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY etc. yahin se uthega.
load_dotenv(override=True)

# pydantic hamare env me guaranteed hai (langchain/openai-agents iski dependency). Typed judge
# verdict (structured output) isi se. (boto3 / langfuse env me NAHI hain — sab lazy + fallback.)
from pydantic import BaseModel, Field  # noqa: E402  (load_dotenv ke baad — Ed style)


# ===========================================================================
# get_client — judge ke liye LLM. EXACT helper (placeholder fix ke saath).
# ===========================================================================
# Groq/Gemini OpenAI-compatible hain — sirf base_url alag. Wahi ek `openai` library teeno ko
# call kar leti hai. LLM-as-a-Judge ka "LLM" yahin se aata hai (key na ho to use hi nahi karte).
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
# ############  PART 1 — TRACING / SPANS (L111 ka `observe` wrapper analog) ##
# ===========================================================================
# Ed ka `with observe(): ...` Langfuse ko behind-the-scenes set up karke har LLM/tool call ko
# ek SPAN ki tarah log karta tha. Is env me langfuse NAHI hai, isliye hum DO tracers banate hain
# ek hi interface ke peeche:
#   1) LangfuseTracer -> LAZY `from langfuse import ...`, REAL path. Missing/no-key => fallback.
#   2) LocalTracer    -> structured JSON spans PRINT + ek nested trace-tree rakhta. OFFLINE, $0.
# `trace(name)` ek context-manager (with-block) AUR decorator dono ki tarah use ho sakta hai.


@dataclass
class Span:
    """Ek single span = trace ke andar ek named sub-operation ka record.
    WHY ye fields: yahi cheezein debugging me chahiye hoti hain —
      name        = kaun sa step (e.g. 'planner', 'reporter', 'judge')
      input/output= step me kya andar gaya, kya bahar aaya (agent-to-agent conversation)
      latency_ms  = step ne kitna time liya (slow agent dhoondhne ke liye)
      metadata    = extra tags (model, tokens, score) — dashboards/filter ke liye
      children    = nested spans (planner ke andar reporter, reporter ke andar judge) => trace-tree
      status      = 'ok' / 'error' (span fail to nahi hua)"""
    name: str
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    input: object = None
    output: object = None
    latency_ms: float = 0.0
    metadata: dict = field(default_factory=dict)
    status: str = "ok"
    children: list = field(default_factory=list)

    def to_dict(self):
        """JSON-serializable dict — structured logging ka core (L109: JSON logs query-friendly)."""
        return {
            "span": self.name,
            "span_id": self.span_id,
            "latency_ms": round(self.latency_ms, 2),
            "status": self.status,
            "input": self.input,
            "output": self.output,
            "metadata": self.metadata,
            "children": [c.to_dict() for c in self.children],
        }


class LocalTracer:
    """OFFLINE fallback (Ed ke `observe` wrapper ka local analog). Langfuse na ho to yeh har span
    ko structured JSON me PRINT karta hai AUR ek nested trace-tree memory me rakhta hai.
    WHY nested tree: real agent runs nested hote hain (planner -> reporter -> judge). Hum ek
    _stack rakhte hain: jab naya span khulta hai, current span ke 'children' me push hota; band
    hone par stack se pop. Isse pura trace-tree ban jaata bina kisi cloud ke. KOI network, $0."""

    name = "local-tracer"

    def __init__(self, emit_json=True):
        self.roots = []          # list[Span] — top-level traces (jinka koi parent nahi)
        self._stack = []         # currently-open spans (LIFO) — nesting track karne ke liye
        self.emit_json = emit_json

    @contextmanager
    def span(self, name, input=None, metadata=None):
        """Ek span khol do. with-block ke andar jo bhi ho wo is span me record. Block khatam
        hone par latency calculate karke JSON print + tree me attach. yield ek SpanHandle deta
        hai taaki andar se .set_output()/.set_metadata() call kar sako (Langfuse span.score jaisa)."""
        sp = Span(name=name, input=input, metadata=dict(metadata or {}))
        # Nesting: agar koi span pehle se open hai, yeh uska child hai; warna ek naya root trace.
        if self._stack:
            self._stack[-1].children.append(sp)
        else:
            self.roots.append(sp)
        self._stack.append(sp)
        start = time.perf_counter()
        handle = _SpanHandle(sp)
        try:
            yield handle
        except Exception as e:
            # Span fail hua => status mark karo par exception ko aage badhne do (caller decide kare).
            sp.status = "error"
            sp.metadata["error"] = f"{type(e).__name__}: {e}"
            raise
        finally:
            sp.latency_ms = (time.perf_counter() - start) * 1000.0
            self._stack.pop()
            if self.emit_json:
                # Structured JSON span print — yahi "log shipping" ka offline analog. Real path me
                # yeh Langfuse server ko jaata; yahan stdout par (CloudWatch JSON logs jaisa).
                indent = "  " * len(self._stack)  # depth ke hisaab se indent (tree feel)
                print(f"{indent}[span] {json.dumps(_shallow(sp.to_dict()), ensure_ascii=True)}")


class _SpanHandle:
    """with trace(...) as t:  ke andar `t` — span ko output/metadata se enrich karne ka handle.
    Langfuse ke span.update()/span.score() ka local analog."""
    def __init__(self, span: Span):
        self._span = span

    def set_output(self, output):
        self._span.output = output

    def set_metadata(self, **kwargs):
        self._span.metadata.update(kwargs)

    def score(self, name, value, comment=None):
        """Langfuse span.score(...) ka analog — span par ek named score chipka do (judge_score).
        Real path me yeh Langfuse me trackable score register karta (L112)."""
        self._span.metadata.setdefault("scores", {})[name] = {"value": value, "comment": comment}


def _shallow(d):
    """JSON print ke liye span ko thoda chhota karo — children ko sirf count me badal do taaki
    har line readable rahe (pura nested tree alag se print hota hai end me, agar chaaho)."""
    out = dict(d)
    out["children"] = f"<{len(d['children'])} child span(s)>"
    # Lambe input/output ko truncate — log line readable rahe (cost/noise control).
    for k in ("input", "output"):
        v = out.get(k)
        if isinstance(v, str) and len(v) > 120:
            out[k] = v[:120] + "...[truncated]"
    return out


class LangfuseTracer:
    """REAL path — Langfuse client via LAZY import (L111). Is env me langfuse NAHI hai, isliye
    yeh class kabhi actually activate nahi hogi; bas dikhane ke liye ki REAL trace kaisa hota
    aur graceful-degrade kaise hota. `make_tracer()` isko try karke fail hone par LocalTracer
    par girta hai — caller ko ek hi `span()` interface milta (provider abstraction)."""

    name = "langfuse"

    def __init__(self):
        # LAZY import — module top par NAHI. langfuse missing => poori file crash na ho.
        try:
            from langfuse import Langfuse  # noqa: F401  (lazy on purpose)
        except ImportError as e:
            raise RuntimeError(
                "langfuse package missing => Langfuse tracing use nahi ho sakta. "
                f"-> LocalTracer fallback. (detail: {e})"
            )
        # Keys check — Ed ka feature-flag-by-env-var pattern (L111): secret key na ho to off.
        if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
            raise RuntimeError(
                "LANGFUSE_PUBLIC_KEY/SECRET set nahi => Langfuse off (feature-flag-by-env-var). "
                "-> LocalTracer fallback."
            )
        # Yahan REAL client banta (sirf reference — is env me pahunchega hi nahi):
        #   self._lf = Langfuse(public_key=..., secret_key=..., host=os.getenv("LANGFUSE_HOST"))
        raise RuntimeError("Langfuse client is reference-only in this offline lab.")

    @contextmanager
    def span(self, name, input=None, metadata=None):
        # Real path: with self._lf.start_as_current_span(name=name, input=input) as s: yield ...
        raise RuntimeError("Langfuse span is reference-only in this offline lab.")


def make_tracer():
    """CONFIG decide karta hai kaun chalega (provider-abstraction). LANGFUSE keys set hain =>
    Langfuse try; package/keys missing ho to clean Hinglish note ke saath LocalTracer.
    Default (keys unset) => seedha LocalTracer (offline/$0 path)."""
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        try:
            return LangfuseTracer()
        except RuntimeError as e:
            print(f"[INFO] {e}")
            print("[INFO] Langfuse unavailable => LocalTracer (offline JSON spans, $0) par switch.")
    return LocalTracer()


# Module-level default tracer — taaki `trace(name)` decorator/CM ko har baar tracer na dena pade.
# (Self-demo isko reset bhi kar sakta hai taaki har run ka tree clean ho.)
_TRACER = make_tracer()


@contextmanager
def trace(name, input=None, metadata=None):
    """PUBLIC API — context-manager: `with trace("planner") as t: ... t.set_output(...)`.
    Yeh Ed ke `with observe()` / `with trace(...)` ka analog hai. Default global tracer use karta
    (Langfuse if keys, warna LocalTracer). Spans nested ho sakte hain (with ke andar with)."""
    with _TRACER.span(name, input=input, metadata=metadata) as handle:
        yield handle


def traced(name=None):
    """PUBLIC API — DECORATOR form: @traced("reporter") def reporter(...): ...
    Function ko ek span me wrap kar deta hai (args -> input, return -> output). WHY decorator bhi:
    kabhi-kabhi har function ko manually with-block me wrap karna boilerplate hota; decorator se
    ek line me poora function instrument ho jaata (jaise OpenAI Agents SDK ka @function_tool tracing)."""
    def deco(fn):
        span_name = name or fn.__name__
        def wrapper(*args, **kwargs):
            # Input ko ek chhote summary me record karte (poore objects nahi — noise/cost control).
            inp = {"args": [str(a)[:80] for a in args], "kwargs": {k: str(v)[:80] for k, v in kwargs.items()}}
            with trace(span_name, input=inp) as t:
                result = fn(*args, **kwargs)
                t.set_output(str(result)[:200])
                return result
        wrapper.__name__ = fn.__name__
        return wrapper
    return deco


# ===========================================================================
# ############  PART 2 — LLM-AS-A-JUDGE (L111/L112 ka `judge`/evaluate)  #####
# ===========================================================================
# Ed ka judge: ek LLM call with STRUCTURED OUTPUT (pydantic) jo kisi answer ki quality evaluate
# karta. Verdict me reasoning PEHLE, score BAAD me (explainable AI, L110/L111). Key na ho => ek
# DETERMINISTIC heuristic judge (length/keyword) — taaki eval pipeline phir bhi chale (offline).


class Verdict(BaseModel):
    """Judge ka typed output (Ed ke `Evaluation{feedback, score}` ka analog).
    FIELD ORDER MATTERS (L110/L111 ka critical trick): `reasoning` PEHLE declare kiya, `score`
    BAAD me. LLM token-by-token generate karta hai => pehle reasoning sochega, phir uske consistent
    score dega. Ulta karte (score pehle) to reasoning sirf post-hoc justification ban jaata."""
    reasoning: str = Field(description="Step-by-step rationale for the score (BEFORE the score).")
    score: int = Field(ge=1, le=5, description="Quality score 1 (poor) to 5 (excellent).")
    # `passed` = ek derived guardrail flag. Ed L112 me 0.3 (of 1.0) threshold use karta => yahan
    # 1-5 scale par equivalent ~ score >= 3 (60%). Yeh response ko user tak jaane dena/rokna decide.
    passed: bool = Field(description="True if score meets the quality bar (>= pass threshold).")


PASS_THRESHOLD = 3   # 1-5 scale par "acceptable" (Ed ke 0.3-of-1.0 guardrail ke roughly equivalent)

JUDGE_SYSTEM = (
    "You are a strict evaluation agent. You judge the quality of an ANSWER to a QUESTION "
    "against the given CRITERIA. First write concise step-by-step REASONING, THEN give an "
    "integer SCORE from 1 (poor) to 5 (excellent), THEN a boolean PASSED (true if the answer "
    "is acceptable). Reasoning must come before the score (explainable AI)."
)


def _heuristic_judge(question: str, answer: str, criteria: str) -> Verdict:
    """NO-KEY fallback: deterministic length/keyword-based judge. Asli LLM nahi, par eval pipeline
    ko chalu rakhta hai (offline) AUR dikhata hai ki ek cheap rule-based 'judge' kaisa hota.
    WHY rule-based bhi useful: production me aksar heuristic guardrails (cost/latency $0) ko LLM-judge
    ke SAATH layer karte — sasta filter pehle, mehenga LLM-judge sirf borderline cases par.
    Scoring logic (transparent, deterministic):
      +base 1
      +1 agar answer thoda substantial (>= 8 words)  -> empty/one-word answers ko penalize
      +1 agar answer me question ke key terms overlap karte (relevance ka proxy)
      +1 agar koi citation/structure clue ho ([source / : / number) -> groundedness ka proxy
      +1 agar answer na to bahut chhota na bahut bada (40-600 chars) -> "just right" length
    score 1..5 me clamp. passed = score >= PASS_THRESHOLD."""
    a = (answer or "").strip()
    words = a.split()
    score = 1
    reasons = []

    if len(words) >= 8:
        score += 1
        reasons.append("answer is substantial (>=8 words)")
    else:
        reasons.append("answer is too short (<8 words) -> likely low quality")

    # Relevance proxy: question ke 'content words' (len>3) answer me kitne aate hain.
    q_terms = {w.lower().strip("?.,") for w in question.split() if len(w) > 3}
    a_lower = a.lower()
    overlap = sum(1 for t in q_terms if t in a_lower)
    if q_terms and overlap >= max(1, len(q_terms) // 3):
        score += 1
        reasons.append(f"relevant to question ({overlap}/{len(q_terms)} key terms present)")
    else:
        reasons.append("low term overlap with question -> may be off-topic")

    # Groundedness/structure proxy: citation/colon/number jaisa koi signal.
    if "[source" in a_lower or ":" in a or any(ch.isdigit() for ch in a):
        score += 1
        reasons.append("contains citation/structure/number cues (groundedness proxy)")

    # Length sweet-spot.
    if 40 <= len(a) <= 600:
        score += 1
        reasons.append("length is in the readable sweet-spot (40-600 chars)")
    elif len(a) > 600:
        reasons.append("answer very long -> may ramble / cost concern")

    score = max(1, min(5, score))
    reasoning = "HEURISTIC judge (no LLM key): " + "; ".join(reasons) + "."
    return Verdict(reasoning=reasoning, score=score, passed=score >= PASS_THRESHOLD)


def judge_response(question: str, answer: str, criteria: str) -> Verdict:
    """LLM-AS-A-JUDGE (Ed ke evaluate()): answer ko 1-5 score karwao given criteria par.
    Return ek pydantic Verdict {reasoning, score, passed}. Key ho to groq se REAL judge; key na
    ho to deterministic heuristic judge (offline, $0). Live call fail (quota/auth/net) ho to bhi
    heuristic par girta — eval pipeline kabhi crash na kare."""
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return _heuristic_judge(question, answer, criteria)

    client, model = get_client("groq")
    user_prompt = (
        f"CRITERIA: {criteria}\n\n"
        f"QUESTION: {question}\n\n"
        f"ANSWER: {answer}\n\n"
        "Evaluate the answer. Respond ONLY as JSON with keys exactly: "
        '"reasoning" (string), "score" (integer 1-5), "passed" (boolean). '
        "Write reasoning first, then score, then passed."
    )
    try:
        # response_format=json_object => model ko valid JSON par force karte (structured output ka
        # OpenAI-compatible tareeka; openai-agents ke output_type ka light analog).
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=300,
            temperature=0.0,   # judging deterministic ho — har baar same answer same score
        )
        raw = resp.choices[0].message.content
        data = json.loads(raw)
        # pydantic validate karega (score 1-5 range, types) — galat shape par yahin pakad jaayega.
        v = Verdict(
            reasoning=str(data.get("reasoning", "")),
            score=int(data.get("score", 1)),
            passed=bool(data.get("passed", int(data.get("score", 1)) >= PASS_THRESHOLD)),
        )
        return v
    except Exception as e:
        # Network/quota/auth/parse fail => crash mat karo, heuristic par giro (graceful degrade).
        print(f"[INFO] Live judge fail ({type(e).__name__}: {e}) => heuristic judge fallback.")
        return _heuristic_judge(question, answer, criteria)


# ===========================================================================
# ############  CLOUDWATCH-STYLE METRIC EMIT (L109)  ########################
# ===========================================================================
# L109 me Ed ne CloudWatch dashboards (judge_score jaisa custom metric is par dashboard/alarm ban
# sakta). Real path = boto3 cloudwatch.put_metric_data (LAZY). boto3/AWS na ho => ek structured
# "[metric]" line print (offline). Yahi metric prod me "Agent Quality" dashboard ko feed karta.
def emit_cloudwatch_metric(metric_name: str, value: float, unit="None", dimensions=None):
    """judge_score ko ek CloudWatch custom metric ki tarah emit karo. REAL path lazy boto3;
    AWS/creds/boto3 na ho to ek JSON metric-line print (CloudWatch JSON-log embedded-metric jaisa).
    NEVER network/crash — fail to bhi sirf print."""
    dims = dimensions or {"AgentSystem": "alex-financial-planner"}
    try:
        import boto3  # noqa: F401  (lazy on purpose)
        # Creds check — boto3 import ho bhi gaya to bina creds ke network call hang/fail kar sakta.
        if not (os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")):
            raise RuntimeError("AWS creds missing")
        # Yahan REAL call hota (sirf reference — is env me pahunchega hi nahi):
        #   cw = boto3.client("cloudwatch", region_name=os.getenv("AWS_REGION", "us-east-1"))
        #   cw.put_metric_data(Namespace="Alex/AgentQuality", MetricData=[{
        #       "MetricName": metric_name, "Value": value, "Unit": unit,
        #       "Dimensions": [{"Name": k, "Value": v} for k, v in dims.items()]}])
        raise RuntimeError("CloudWatch put_metric_data is reference-only in this offline lab.")
    except (ImportError, RuntimeError) as e:
        # OFFLINE: ek structured metric line. Prod me yeh CloudWatch -> dashboard widget -> alarm.
        line = {"metric": metric_name, "value": round(value, 4), "unit": unit, "dimensions": dims}
        print(f"  [metric] {json.dumps(line, ensure_ascii=True)}  "
              f"(boto3/AWS na mila => offline print; reason: {type(e).__name__})")


# ===========================================================================
# ############  A SMALL INSTRUMENTED AGENT (tracing ko dikhane ke liye)  ####
# ===========================================================================
# Ed ka planner -> reporter -> judge flow ka chhota offline analog. Hum ek 2-agent "research"
# pipeline banate hain (retriever + writer), poora ek trace ke andar, taaki LocalTracer nested
# spans dikha sake. KOI LLM zaroori nahi — yeh deterministic stub agents hain (focus = tracing).
# (Asli RAG Week-3 Lab5 me hai; yahan sirf observability instrument karna sikhana hai.)

_FAKE_KB = {
    "rag": "RAG retrieves relevant context, augments the prompt, then generates a grounded, "
           "cited answer so the model does not hallucinate.",
    "observability": "Observability is monitoring on steroids: traces, spans, tokens and "
                     "agent-to-agent conversations give deep insight into agent internals.",
    "guardrail": "A guardrail validates input/output around an agent; an LLM-as-a-Judge "
                 "guardrail blocks a low-score response and returns a safe fallback.",
}


def _retriever_agent(question: str) -> str:
    """Stub 'retriever' agent — keyword match karke _FAKE_KB se ek context laata. (Ed ke
    reporter ke 'Get Market Insights' tool ka offline analog — focus tracing par hai, RAG par nahi.)"""
    time.sleep(0.01)   # thoda kaam simulate (latency span me dikhe) — itna chhota ki demo fast rahe
    q = question.lower()
    for key, ctx in _FAKE_KB.items():
        if key in q:
            return ctx
    return "No specific context found in the local knowledge base."


def _writer_agent(question: str, context: str) -> str:
    """Stub 'writer' agent — context se ek short answer 'compose' karta. (Asli me yeh LLM hota.)"""
    time.sleep(0.01)
    return f"{context} [source: local-kb]"


def run_agent(question: str) -> str:
    """Ek chhota multi-agent run, POORA tracing ke andar. Yeh dikhata hai trace-TREE kaisa banta:
        agent-run (root span)
          |- retrieve (child span: input=question, output=context, latency)
          |- write    (child span: input=context, output=answer, latency)
    Yahi shape Langfuse me dikhta (planner ke andar reporter/charter, L112 timeline view)."""
    with trace("agent-run", input={"question": question}, metadata={"pipeline": "retrieve->write"}) as root:
        # Span 1: retrieve
        with trace("retrieve", input={"question": question}) as t1:
            context = _retriever_agent(question)
            t1.set_output(context)
            t1.set_metadata(kb_hit=context.startswith("No ") is False)
        # Span 2: write (retrieve ke output ko input ki tarah leta — agent-to-agent conversation)
        with trace("write", input={"context": context}) as t2:
            answer = _writer_agent(question, context)
            t2.set_output(answer)
            t2.set_metadata(model="stub-writer")
        root.set_output(answer)
        return answer


# ===========================================================================
# ############  AUTOMATED EVAL SUITE (L112 ka judge-wired-into-handler)  ####
# ===========================================================================
# L112: judge ko reporter ke handler me wire kiya — score register + event + guardrail. Yahan hum
# judge ko ek EVAL SUITE ki tarah kuch sample Q/A pairs par chalate hain (regression-test style),
# har judging ko ek span me wrap karte (Langfuse span 'judge'), judge_score ko CloudWatch metric
# ki tarah emit karte, aur guardrail (passed?) check karte. Yeh "continuous quality eval" hai.

# Sample Q/A pairs — ek deliberately GOOD, ek WEAK, ek BORDERLINE — taaki judge ka discrimination
# (alag scores) dikhe. (Production me yeh ek "golden dataset" hota — L112 ka 'datasets' feature.)
EVAL_PAIRS = [
    {
        "question": "What is RAG and why does it reduce hallucination?",
        "answer": ("RAG retrieves relevant context, augments the prompt with it, then generates "
                   "a grounded answer that cites its sources [source: doc1], so the model relies "
                   "on provided evidence instead of its memory."),
        "criteria": "Correctly explains retrieve-augment-generate AND why it reduces hallucination; cited.",
    },
    {
        "question": "What is observability for AI agents?",
        "answer": "Dunno.",   # deliberately weak — judge ko FAIL karna chahiye (guardrail trigger)
        "criteria": "Defines observability, distinguishes it from monitoring, mentions traces/spans.",
    },
    {
        "question": "How does an LLM-as-a-Judge guardrail protect users?",
        "answer": ("It scores the answer and blocks low-quality responses, sending a safe fallback."),
        "criteria": "Explains scoring + blocking below a threshold + safe fallback to the user.",
    },
]


def run_eval_suite(pairs, tracer_label=""):
    """Judge ko ek automated eval ki tarah chala (L112 flow): har pair par ek 'judge' span kholo,
    judge_response() chalao, span.score() register karo, judge_score CloudWatch metric emit karo,
    aur guardrail (passed?) check karo. Return aggregate metrics (avg score, pass rate)."""
    results = []
    for i, p in enumerate(pairs, 1):
        # Har eval ek 'judge' span ke andar (L112: with observe.start_span(name="judge")).
        with trace("judge", input={"q": p["question"], "a": p["answer"]},
                   metadata={"criteria": p["criteria"]}) as jspan:
            verdict = judge_response(p["question"], p["answer"], p["criteria"])
            # Langfuse span.score() ka analog — score span par register.
            jspan.score("judge_score", value=verdict.score, comment=verdict.reasoning[:80])
            jspan.set_output({"score": verdict.score, "passed": verdict.passed})

        # Human-readable summary (span JSON ke alag, padhne ke liye).
        print(f"\n  --- eval {i}/{len(pairs)} ---")
        print(f"  Q       : {p['question']}")
        print(f"  A       : {p['answer'][:90]}{'...' if len(p['answer']) > 90 else ''}")
        print(f"  score   : {verdict.score}/5   passed={verdict.passed}")
        print(f"  reason  : {verdict.reasoning[:140]}{'...' if len(verdict.reasoning) > 140 else ''}")

        # GUARDRAIL (L112): passed na ho to response BLOCK karke safe fallback (yahan demonstrate).
        if not verdict.passed:
            print("  GUARDRAIL: score below pass bar => response BLOCKED, safe fallback bheja jaata: "
                  "\"I'm sorry, I'm not able to generate a quality answer. Please try again later.\"")

        # CloudWatch-style metric emit (L109): judge_score ko ek dashboard/alarm metric ki tarah.
        emit_cloudwatch_metric("judge_score", float(verdict.score), unit="None",
                               dimensions={"AgentSystem": "alex-financial-planner", "eval": f"pair{i}"})

        results.append(verdict)

    # Aggregate metrics — yeh "Agent Quality" dashboard ki summary tiles hoti (avg + pass-rate).
    avg = sum(v.score for v in results) / len(results)
    pass_rate = sum(1 for v in results if v.passed) / len(results)
    return {"avg_score": avg, "pass_rate": pass_rate, "n": len(results), "verdicts": results}


# ===========================================================================
# SELF-DEMO — `uv run <file>` (no args) yahan. No key/langfuse/AWS/download => exit 0.
# ===========================================================================
def run_self_demo():
    print("\n" + "#" * 74)
    print("#  LAB 4 SELF-DEMO — Observability: tracing (spans) + LLM-as-a-Judge eval")
    print("#  (no key / no langfuse / no AWS / no download bhi OK — exit 0)")
    print("#" * 74 + "\n")

    # --- Setup: tracer (Langfuse if keys, warna LocalTracer) ----------------
    global _TRACER
    _TRACER = make_tracer()   # fresh tracer => clean trace-tree har run
    print("=" * 74)
    print("SETUP  (tracer = Ed ke `with observe()` wrapper ka analog — L111)")
    print("=" * 74)
    print(f"tracer        = {_TRACER.name}")
    judge_mode = "LIVE LLM (GROQ_API_KEY mila)" if os.getenv("GROQ_API_KEY") else "HEURISTIC (no key)"
    print(f"judge mode    = {judge_mode}")
    if _TRACER.name == "local-tracer":
        print("note          = LANGFUSE_PUBLIC_KEY/SECRET nahi mile => LocalTracer (offline JSON "
              "spans, $0). Real Langfuse = lazy import + keys (L111).")
    print()

    # --- PART 1: trace a sample agent run (LocalTracer prints nested spans) --
    print("=" * 74)
    print("PART 1  — TRACE A SAMPLE AGENT RUN  (nested spans = trace-tree, L112 timeline analog)")
    print("=" * 74)
    print("run_agent('...') ek 2-agent pipeline hai (retrieve -> write), poora ek trace me.")
    print("Niche har span ka structured JSON print hota hai (indent = nesting depth):\n")
    answer = run_agent("What is observability for AI agents?")
    print(f"\n  agent final answer: {answer}\n")
    print("  ^ Dekho: 'agent-run' (root) ke andar 'retrieve' + 'write' child spans, har ek ka")
    print("    latency_ms + input/output + metadata. Yahi multi-agent debugging ka core hai —")
    print("    KAUN sa step, KITNA time, KYA I/O. (Real Langfuse me yeh timeline + tree view.)\n")

    # --- PART 2: LLM-as-a-Judge over sample Q/A pairs (automated eval) -------
    print("=" * 74)
    print("PART 2  — LLM-AS-A-JUDGE EVAL SUITE  (L111/L112: judge -> span.score -> guardrail)")
    print("=" * 74)
    print("Judge ko 3 sample answers par chalate hain (1 good, 1 weak, 1 borderline). Har eval")
    print("ek 'judge' span me, score span par register, judge_score CloudWatch metric ki tarah")
    print("emit, aur guardrail (passed?) check. Verdict = pydantic {reasoning, score, passed}")
    print("(reasoning PEHLE => explainable AI, L110/L111 ka 'rationale-first' trick).")
    summary = run_eval_suite(EVAL_PAIRS)

    # --- Aggregate metrics + dashboard/alarm framing ------------------------
    print("\n" + "=" * 74)
    print("AGGREGATE QUALITY METRICS  (L109 dashboard + alarm framing)")
    print("=" * 74)
    print(f"  evaluated     = {summary['n']} answers")
    print(f"  avg_score     = {summary['avg_score']:.2f} / 5")
    print(f"  pass_rate     = {summary['pass_rate'] * 100:.0f}%  (passed = score >= {PASS_THRESHOLD})")
    # Ek aggregate metric bhi emit — yeh "Agent Quality" dashboard ki main tile + alarm ka source.
    emit_cloudwatch_metric("avg_judge_score", summary["avg_score"], unit="None",
                           dimensions={"AgentSystem": "alex-financial-planner", "window": "eval-suite"})
    # ALARM framing (L110): threshold cross => page/email.
    ALARM_MIN_AVG = 3.0
    if summary["avg_score"] < ALARM_MIN_AVG:
        print(f"  ALARM         : avg_judge_score {summary['avg_score']:.2f} < {ALARM_MIN_AVG} "
              "=> CloudWatch alarm FIRE (prod me: email/SNS page on-call, L110).")
    else:
        print(f"  ALARM         : avg_judge_score >= {ALARM_MIN_AVG} => OK, koi alarm nahi.")
    print()

    # --- Teaching: Langfuse vs CloudWatch -----------------------------------
    print("=" * 74)
    print("LANGFUSE vs CLOUDWATCH  (do alag observability layers — L109 vs L111/L112)")
    print("=" * 74)
    print("- Langfuse  = LLM-NATIVE traces: prompts, completions, tokens, agent-to-agent")
    print("              conversations, judge scores. 'Monitoring on steroids' (internals).")
    print("- CloudWatch= INFRA metrics: Lambda duration, error rate, invocations, throttles,")
    print("              dashboards + ALARMS (threshold -> email/page). Predefined knowns.")
    print("- Saath chalte hain: Langfuse 'kya bola/socha', CloudWatch 'kitna time/kitne errors'.")
    print("- Gotcha (L112): Bedrock model COST Langfuse tak nahi aata => cost AWS me alag (Cost Explorer).")
    print()

    # --- Deploy runbook pointer (L111/L112) ---------------------------------
    print("=" * 74)
    print("DEPLOY RUNBOOK  (real cloud — L111/L112)")
    print("=" * 74)
    print("trace() ka real path = Langfuse client (keys tfvars se, L111). Agent code `with trace`")
    print("+ `with observe()` me wrap; har LLM/tool call ek span. judge_response() reporter ke")
    print("lambda handler me; span.score('judge', value) Langfuse me register; score<bar => guardrail")
    print("response wipe (L112). judge_score boto3 put_metric_data se CloudWatch 'Agent Quality'")
    print("dashboard + alarm (avg < 3 => page) ko feed karta (L109/L110).")
    print()

    print("#" * 74)
    print("#  LAB 4 complete. trace()=spans (Langfuse/LocalTracer); judge_response()=LLM/heuristic")
    print("#  1-5 verdict; eval-suite + guardrail + CloudWatch metric. Key/langfuse/AWS na ho to")
    print("#  graceful degrade, exit 0. (Week-4 capstone observability + continuous eval.)")
    print("#" * 74 + "\n")

    raise SystemExit(0)


# ===========================================================================
# MAIN — default self-demo; --judge "<q>" "<a>" => ek hi answer ko judge karo.
# ===========================================================================
if __name__ == "__main__":
    if "--judge" in sys.argv:
        idx = sys.argv.index("--judge")
        q = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "What is RAG?"
        a = sys.argv[idx + 2] if idx + 2 < len(sys.argv) else "RAG retrieves then generates."
        crit = "Answer should be accurate, relevant, and grounded."
        _TRACER = make_tracer()
        print(f"[tracer] {_TRACER.name}   [judge] "
              f"{'live' if os.getenv('GROQ_API_KEY') else 'heuristic'}")
        with trace("judge", input={"q": q, "a": a}) as jspan:
            v = judge_response(q, a, crit)
            jspan.score("judge_score", value=v.score, comment=v.reasoning[:80])
            jspan.set_output({"score": v.score, "passed": v.passed})
        print(f"\nVerdict: score={v.score}/5  passed={v.passed}")
        print(f"Reasoning: {v.reasoning}")
        emit_cloudwatch_metric("judge_score", float(v.score),
                               dimensions={"AgentSystem": "ad-hoc"})
        raise SystemExit(0)
    else:
        run_self_demo()
