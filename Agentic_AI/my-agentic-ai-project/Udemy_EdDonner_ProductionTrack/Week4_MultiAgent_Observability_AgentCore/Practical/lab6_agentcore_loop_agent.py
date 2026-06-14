"""
LAB 6 — Bedrock AgentCore + loop-based reasoning agent (COURSE FINALE)
======================================================================
Title: Ek ReAct-style LOOP agent banao — ek while-loop jo (LLM THINKS -> ek TOOL pick kare
       -> TOOL run ho -> OBSERVATION wapas feed -> repeat) jab tak FINAL answer na mile, ek
       max-iters SAFETY cap ke saath (Week-1 lesson). Tools: ek safe AST-based calculator
       (NO eval), ek MOCK code-execution tool (describe-only / restricted), aur ek lookup tool.
       Real path = ek BedrockAgentCoreRunner STUB (LAZY boto3 bedrock-agentcore jab configured)
       jo dikhata hai ki YEHI loop managed AgentCore runtime par kaise map hota. OFFLINE
       fallback = loop ko LOCALLY chalao get_client se (no key => ek SCRIPTED deterministic
       loop taaki mechanics visible rahein). Bina key/boto3/AWS bhi pura chalta + EXIT 0.

KYA SEEKHENGE (what concepts):
- LOOP-BASED (agentic) reasoning VS SINGLE-SHOT (L121 ka "Looper"):
    * SINGLE-SHOT: ek prompt -> ek answer. Multi-step problem (calc -> lookup -> combine) me
      LLM ko sab kuch ek hi baar "head me" karna padta -> aksar galti.
    * LOOP (ReAct = Reason+Act): LLM ek baar me sirf AGLA step sochta hai -> ek TOOL chalata
      hai -> tool ka REAL output (observation) wapas context me aata -> phir agla step. Yeh
      "think -> act -> observe -> repeat" hi wo "to-do list jaisi mystique" hai jo L121 me Ed
      ne demystify ki: actually bas ek loop + kuch tools + ek system prompt.
- MAX-ITERS SAFETY CAP (Week-1 lesson, L121 ka spirit): agar loop kabhi terminal condition
  (final answer) tak na pahunche to INFINITE chalega -> cost + latency blowup. Isliye ek hard
  cap (`max_iters`). Yeh wahi resilience pattern hai jaisa tum kisi retry/poll loop me lagate ho.
- AGENT PLATFORM (Bedrock AgentCore) VS CUSTOM (Lambda/containers/Terraform — jo poora course
  banaya) — L117/L118 ka core tradeoff:
    * AgentCore = MANAGED runtime + Memory + Identity(IAM) + Gateway(tools via MCP) +
      Observability. `agentcore configure` + `agentcore launch` -> minutes me AWS par live.
      Pros: killer time-to-market, batteries-included. Cons: kam flexibility, vendor lock-in,
      sab abhi naya (kai open-source frameworks ki monetization strategy).
    * CUSTOM (course wala): Lambda + ECR + Terraform + fine-grained IAM/scaling/observability.
      Slow setup, par full control + portability. Enterprise prod aaj bhi MOSTLY custom hai;
      platforms startups/experiments ke liye. KEY insight: SAME loop dono jagah chalta hai —
      sirf DEPLOYMENT/scaffolding badalta hai (yeh lab dono ko side-by-side dikhata hai).
- CODE-EXECUTION TOOL SANDBOXING RISK (L118/L122): AgentCore ka managed "Code Interpreter"
  Python ko ek SANDBOX (Docker/gVisor) me chalata hai. WHY sandbox: LLM-generated code
  UNTRUSTED hai — kabhi bhi apne main process me `eval`/`exec` mat karo (RCE, data exfil,
  fork-bomb). Is lab ka `mock_execute_python` JAAN-BOOJH ke describe-only hai (code chalata
  NAHI) — yeh hi safe demo + "asli sandbox AWS deta" ka framing hai.
- OBSERVABILITY (L107/L111/L122): har think/act/observe step ek SPAN hai. Real path = Langfuse
  (LAZY import jab keys set). Offline fallback = ek LOCAL span logger jo structured JSON spans
  print karta (no network) — exactly woh "traces" jisme L122 me Ed ne rate-limit retries pakde.
- COURSE WRAP (L123): production AI ka 60-80% traditional platform engineering hai. Ek choti
  reflection self-demo ke ant me print hoti hai.

KAISE CHALANA (how to run) — CWD = repo root:
    # Default: self-demo (no key / no boto3 / no AWS / no langfuse bhi chalega, EXIT 0)
    uv run Udemy_EdDonner_ProductionTrack/Week4_MultiAgent_Observability_AgentCore/Practical/lab6_agentcore_loop_agent.py

    # Apna ek task poochho (loop ka think->act->observe live dikhega):
    uv run Udemy_EdDonner_ProductionTrack/Week4_MultiAgent_Observability_AgentCore/Practical/lab6_agentcore_loop_agent.py --ask "What is 12.5 * 8, then add the population-millions of india?"

    # Managed path ka shape dekhna ho (boto3 na ho to clean Hinglish note + local fallback):
    AGENTCORE_AGENT_ARN=arn:aws:... uv run .../lab6_agentcore_loop_agent.py

LECTURE MAPPING: Ed Donner "AI Engineer Production Track", Week 4 · Day 5 (L117-L123).
  L117 = Agent platforms VS custom deployment (managed pros/cons, vendor lock-in, enterprise
         abhi bhi custom). -> niche "PLATFORM VS CUSTOM" framing + reflection.
  L118 = Bedrock AgentCore building blocks (AgentCore umbrella = 5 services + 2 tools;
         AgentCore SDK = framework-agnostic wrapper; Starter Toolkit = CLI; Strands framework;
         "single agent with a loop" teaser). -> BedrockAgentCoreRunner stub + service mapping.
  L119 = One-time IAM + observability setup (Agent Access group, 3 policies, model access).
         -> deploy runbook comments.
  L120 = Deploy first agent (`BedrockAgentCoreApp` + Strands `Agent()` + `@app.entrypoint`;
         local `uv run` server :8080 + `curl /invocations`; `configure -e` + `launch` +
         `invoke`; `@tool`). -> stub ka entrypoint/tool shape isi se.
  L121 = Loop-based reasoning ("Looper": 3 to-do tools + system prompt = reasoning loop;
         max-step spirit; train problem solve). -> YEH lab ka DIL (the loop).
  L122 = Code-execution tool + observability (managed Code Interpreter `execute_python`
         us-west-2 sandbox; system-prompt steering; traces/spans; rate-limit retries dikhe).
         -> mock_execute_python (sandbox risk) + local/Langfuse span logger.
  L123 = Course wrap-up (60-80% traditional platform engineering; final assignment = deploy
         to production). -> ant ki reflection.

DEPLOY RUNBOOK (real cloud, jab key/AWS ho) — L119/L120/L122:
  1) One-time: IAM "Agent Access" group + AmazonBedrockFullAccess + AWSCodeBuildAdminAccess +
     BedrockAgentCoreFullAccess; Claude model access; observability enable (L119).
  2) `loop_agent_entrypoint(payload)` ko ek `@app.entrypoint` ke peeche rakho ek `looper.py`
     me (BedrockAgentCoreApp + Strands Agent + ye SAME tools) (L120/L121).
  3) `uv run agentcore configure -e looper.py` (defaults) -> Dockerfile + .bedrock_agentcore.yaml
     ban jaate -> `uv run agentcore launch` (ECR build + runtime deploy) -> `uv run agentcore
     invoke '{"prompt": "..."}'` (cloud par live). Managed Code Interpreter (us-west-2) add
     karo to `mock_execute_python` ki jagah REAL sandboxed `execute_python` aa jaata (L122).

COST: Is lab ko LOCALLY chalana = $0 (AST calculator + in-memory lookup + scripted loop;
  koi key/boto3/AWS/network/download nahi). LLM key ho to groq free-tier (llama-3.3-70b) loop
  drive karta -> phir bhi ~$0. REAL AgentCore deploy: preview me abhi free (L118 warning:
  jaldi PAID hoga -> pricing page khud dekho), phir per-invocation + CodeBuild + ECR storage +
  Code Interpreter sandbox-seconds + Bedrock per-token. Ed ka anumaan: chhota toy ~chand cents/
  ghante; production scale par managed convenience ki extra cost (L117 ka "charge a bit extra").
"""

import ast
import json
import operator
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

# .env load. override=True => .env value shell ki purani value ko jeet jaaye (Ed convention).
# GROQ_API_KEY / AGENTCORE_AGENT_ARN / LANGFUSE_* yahin se uthega (agar set ho).
load_dotenv(override=True)


# ===========================================================================
# get_client — loop ke "THINK" step ke liye LLM. EXACT helper (placeholder fix ke saath).
# ===========================================================================
# Groq/Gemini OpenAI-compatible hain — sirf base_url alag, wahi `openai` library teeno ko
# call kar leti. Loop ka har iteration LLM se sirf AGLA step maangta (next tool + args).
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
# ############  OBSERVABILITY — span logger (L107/L111/L122)  ###############
# ===========================================================================
# Loop ka har think/act/observe ek SPAN hai (OpenTelemetry/X-Ray jaisa trace-tree node).
# Real path = Langfuse (LAZY import jab LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY set ho).
# Offline fallback = LocalSpanLogger jo structured JSON spans STDOUT par print karta (no
# network). Yehi woh "traces" hai jisme L122 me Ed ne rate-limit retries / slowness pakda.

class LocalSpanLogger:
    """OFFLINE observability — har span ko ek structured JSON line ki tarah print karta.
    WHY local default: is env me langfuse NAHI + koi network allowed nahi. Phir bhi spans ka
    SHAPE (name, input, output, duration_ms) bilkul wahi hota jo managed tracer bhejta —
    taaki tum trace-tree padhna sikho (L122 ka observability lesson)."""

    name = "local-spans"

    def __init__(self):
        self._n = 0

    def span(self, name, kind, payload):
        """Ek span emit karo. kind = think|act|observe|final (trace-tree me color jaisa)."""
        self._n += 1
        rec = {"span": self._n, "name": name, "kind": kind, **payload}
        # Compact single-line JSON => grep/parse karna aasan (real log shippers JSON line khaate).
        print(f"    [span] {json.dumps(rec, default=str)}")


class LangfuseSpanLogger:
    """REAL path — Langfuse (LAZY import). Is env me langfuse NAHI, isliye `make_tracer()`
    isko try karke import-fail par LocalSpanLogger par girta. Caller ko ek hi `span()`
    interface milta (provider abstraction, L84/L111). Yeh class kabhi actually invoke nahi
    hogi yahan — bas dikhaata ki REAL tracer kaise plug hota."""

    name = "langfuse"

    def __init__(self):
        # LAZY import — module top par NAHI, taaki langfuse missing ho to poori file crash na ho.
        from langfuse import Langfuse  # noqa: F401  (lazy on purpose; raises if absent)
        self._client = Langfuse()

    def span(self, name, kind, payload):
        # REAL me yahan self._client.start_span(name=..., input=..., output=...) jaisa hota
        # (Langfuse SDK version par depend). Reference-only — is offline lab me pahunchega hi nahi.
        raise RuntimeError("Langfuse span is reference-only in this offline lab.")


def make_tracer():
    """CONFIG decide karta hai kaun chalega (L111 ka provider-abstraction). LANGFUSE keys set
    hon => Langfuse try; import/creds fail ho to clean Hinglish note ke saath LocalSpanLogger.
    Default (keys unset) => seedha LocalSpanLogger (offline, no network)."""
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        try:
            return LangfuseSpanLogger()
        except Exception as e:  # ImportError ya init fail — dono ko graceful handle
            print(f"[INFO] Langfuse unavailable ({type(e).__name__}: {e})")
            print("[INFO] => LocalSpanLogger (offline JSON spans, $0, no network) par switch.")
    return LocalSpanLogger()


# ===========================================================================
# ############  TOOLS — agent ko jo "haath" milte hain  #####################
# ===========================================================================
# L120/L121/L122 me tools `@tool` decorated functions the (Strands). Yahan hum plain Python
# functions rakhte hain + ek manual TOOL REGISTRY, taaki tum dekho `@tool` ke neeche actually
# bas ek naam->callable + description (schema) ka mapping hai. Teen tools:
#   1) calculate(expr)         -> SAFE AST-based math (NO eval). Week-1 ka safe-calc spirit.
#   2) lookup(key)             -> ek chhota in-memory knowledge base (mock retrieval/Gateway).
#   3) mock_execute_python(..) -> DESCRIBE-ONLY code-exec (sandbox risk teaching; chalata NAHI).


# ---- TOOL 1: SAFE CALCULATOR (AST-based, NO eval) -------------------------
# WHY AST aur NOT eval: `eval("__import__('os').system('rm -rf /')")` bhi "math" jaisa dikh
# sakta hai. eval poora Python execute karta => RCE. Hum input ko AST me PARSE karke sirf
# WHITELISTED nodes (numbers + + - * / ** % aur unary -) allow karte hain. Koi naam/call/
# attribute nahi => arbitrary code IMPOSSIBLE. Yeh wahi "input validation" hai jo tum kisi
# untrusted expression evaluator me lagaoge.
_ALLOWED_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_ALLOWED_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_eval_node(node):
    """Ek AST node ko recursively evaluate karo — SIRF whitelisted shapes. Kuch aur mila =>
    ValueError (refuse). Yeh deny-by-default approach hai (security ka golden rule)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](_safe_eval_node(node.left), _safe_eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:
        return _ALLOWED_UNARY[type(node.op)](_safe_eval_node(node.operand))
    # Naam, function-call, attribute, subscript — sab BLOCKED (yahi RCE ka rasta band karta hai).
    raise ValueError(f"Unsupported/forbidden expression node: {type(node).__name__}")


def calculate(expr: str) -> str:
    """TOOL: ek arithmetic expression evaluate karo SAFELY (NO eval). e.g. "12.5 * 8".
    Return ek string (tools always string return karte taaki observation text-feedable ho)."""
    try:
        tree = ast.parse(expr, mode="eval")  # mode="eval" => single expression only (no stmts)
        result = _safe_eval_node(tree.body)
        return str(result)
    except Exception as e:
        # Tool ERROR ko bhi ek normal observation banao (crash mat karo) — agent retry/adjust kare.
        return f"ERROR: could not evaluate '{expr}' safely ({type(e).__name__}: {e})"


# ---- TOOL 2: LOOKUP (mock knowledge base / Gateway-style retrieval) -------
# L118 ka "Gateway" service tools/data ko MCP ke through expose karta hai. Yahan ek chhota
# in-memory KB ek aise tool ko mimic karta jo kisi DB/API se fact laata (multi-step problem
# me agent pehle calc karta phir lookup karta phir combine — yahi loop ka point hai).
_KNOWLEDGE_BASE = {
    "population-millions of india": "1428",
    "population-millions of usa": "340",
    "speed of light km/s": "299792",
    "agentcore services count": "5",
}


def lookup(key: str) -> str:
    """TOOL: ek known fact uthao (case-insensitive, trimmed). Na mile to saaf 'not found'
    observation (agent ko galat guess karne se bachata)."""
    val = _KNOWLEDGE_BASE.get(key.strip().lower())
    if val is None:
        keys = ", ".join(sorted(_KNOWLEDGE_BASE))
        return f"NOT_FOUND: '{key}'. Available keys: {keys}"
    return val


# ---- TOOL 3: MOCK CODE-EXECUTION (describe-only — sandbox risk teaching) ---
# L118/L122 ka managed "Code Interpreter": Python ko ek SANDBOX (Docker/gVisor, us-west-2) me
# chalata hai aur result wapas deta. WHY sandbox: LLM-generated code UNTRUSTED hai. Is lab me
# hum JAAN-BOOJH ke code CHALATE NAHI — bas describe karte (ki AWS ise sandbox me kaise chalata
# aur kyun apne process me `exec` karna khatarnak hai). Yeh hi "safe demo" + teaching.
def mock_execute_python(code: str) -> str:
    """TOOL (DESCRIBE-ONLY): ek code-exec request ko ACKNOWLEDGE karta hai par ACTUALLY RUN
    NAHI karta. WHY: untrusted/LLM-generated code ko apne main process me exec karna = RCE/
    data-exfil/fork-bomb ka rasta. Real prod me yeh ek MANAGED sandbox (AgentCore Code
    Interpreter, us-west-2) ko bhejta hota jahaan code isolated container me chalta. Yahan hum
    sirf describe karte taaki sandboxing ka concept clear ho bina koi risk liye."""
    preview = code.strip().replace("\n", " ")
    if len(preview) > 80:
        preview = preview[:80] + "..."
    return (
        "SANDBOX_STUB: code received but NOT executed locally (security). "
        f"received_code=`{preview}`. "
        "In production this would run in AgentCore's managed Code Interpreter "
        "(isolated Docker sandbox, us-west-2) and return the real stdout. "
        "NEVER exec untrusted/LLM-generated code in your own process."
    )


# TOOL REGISTRY — naam -> (callable, description). Yeh hi woh "schema" hai jo `@tool` decorator
# docstring+type-hints se auto-banata (L120). LLM ko hum yeh list dete taaki wo jaane konse
# tools available hain aur kab use karna hai.
TOOLS = {
    "calculate": (calculate, "calculate(expr): safely evaluate an arithmetic expression, e.g. '12.5 * 8'. Returns the number as a string."),
    "lookup": (lookup, "lookup(key): fetch a known fact from the knowledge base by key (e.g. 'population-millions of india')."),
    "mock_execute_python": (mock_execute_python, "mock_execute_python(code): request code execution. NOTE: describe-only stub, does not actually run code."),
    # "finish" ek pseudo-tool hai jo loop ko TERMINATE karta — agent isko call karke final answer deta.
    "finish": (None, "finish(answer): provide the FINAL answer to the user and stop the loop."),
}


def run_tool(name: str, args: dict) -> str:
    """Ek tool dispatch karo registry se. Unknown tool / galat args ko ERROR observation
    banao (crash mat karo) — agent ko self-correct karne ka mauka milta hai (resilience)."""
    if name not in TOOLS:
        return f"ERROR: unknown tool '{name}'. Available: {', '.join(TOOLS)}"
    fn = TOOLS[name][0]
    if fn is None:  # "finish" — yahan call nahi hota, loop ise alag handle karta
        return args.get("answer", "")
    try:
        # Single positional arg pattern (calculate/lookup/mock_execute_python sabhi ek arg lete).
        # args dict me jo bhi single value ho usse pass karte (LLM kabhi 'expr' kabhi 'input' bhej de).
        arg_val = next(iter(args.values())) if args else ""
        return str(fn(arg_val))
    except Exception as e:
        return f"ERROR: tool '{name}' failed ({type(e).__name__}: {e})"


# ===========================================================================
# ############  THE LOOP — ReAct: think -> act -> observe -> repeat  ########
# ===========================================================================
# Yeh lab ka DIL (L121 ka "Looper" ka mechanics). Har iteration:
#   1) THINK  : LLM (ya scripted fallback) ko current goal + ab tak ki observations do ->
#               wo ek single JSON step return kare: {"tool": <name>, "args": {...}, "thought": ...}
#   2) ACT    : us tool ko chalao (run_tool).
#   3) OBSERVE: tool ka output (observation) ko transcript me add karo.
#   ...repeat jab tak tool == "finish" (terminal) ya max_iters hit (SAFETY cap).
# Har step ek SPAN emit karta (observability). max_iters = infinite-loop / cost brake (Week-1).

SYSTEM_PROMPT = (
    "You are a loop-based reasoning agent (ReAct style). At EACH step, think about the single "
    "NEXT action and reply with ONLY a JSON object: "
    '{"thought": "...", "tool": "<calculate|lookup|mock_execute_python|finish>", "args": {...}}. '
    "Use 'calculate' for arithmetic, 'lookup' for known facts, 'mock_execute_python' to request "
    "code execution, and 'finish' with {\"answer\": \"...\"} when you have the final answer. "
    "Do not output anything except the JSON object."
)


def _llm_next_step(client, model, goal, transcript):
    """THINK via REAL LLM (groq). transcript = ab tak ke (thought/act/observation) ki history.
    LLM se ek JSON step maangte. Parse fail / network fail => None (caller scripted par girega)."""
    # Transcript ko ek readable history string me badlo (LLM ke liye context).
    history = "\n".join(
        f"step {i + 1}: tool={s['tool']} args={s['args']} -> observation: {s['observation']}"
        for i, s in enumerate(transcript)
    ) or "(no steps yet)"
    user = (
        f"GOAL: {goal}\n\nHISTORY:\n{history}\n\n"
        "Reply with ONLY the next-step JSON object."
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": user}],
            max_tokens=200,
            temperature=0.0,  # deterministic stepping (grounded, low creativity)
        )
        raw = resp.choices[0].message.content.strip()
        # LLM kabhi ```json ... ``` me wrap karta — woh fences hata do, phir parse.
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw[raw.find("{"):raw.rfind("}") + 1]
        return json.loads(raw)
    except Exception as e:
        print(f"    [INFO] Live LLM step fail ({type(e).__name__}: {e}) => scripted fallback.")
        return None


def _scripted_next_step(goal, transcript):
    """OFFLINE deterministic THINK — no key/network. Ek chhoti rule-based "policy" jo loop ke
    MECHANICS dikhati hai (asli LLM ki jagah). WHY scripted (na random): self-demo har machine
    par bilkul same think->act->observe sequence de, taaki teaching reproducible ho.

    Yeh policy baked-in demo task ke around tuned hai ('X * Y, then add lookup-fact'):
      step0: calculate the arithmetic part
      step1: lookup the named fact
      step2: calculate (sum of the two numbers)
      step3: finish with the final number
    Agar koi unexpected goal aaye to gracefully ek best-effort calculate/finish karta."""
    n = len(transcript)
    low = goal.lower()

    # Helper: goal me se pehla "A op B" arithmetic phrase nikaalo (bahut simple heuristic).
    def _first_arith():
        import re
        m = re.search(r"(-?\d+\.?\d*)\s*([*x/+\-])\s*(-?\d+\.?\d*)", low)
        if m:
            op = "*" if m.group(2) == "x" else m.group(2)
            return f"{m.group(1)} {op} {m.group(3)}"
        return None

    # Helper: goal me se ek known KB key dhundho (jo bhi substring match kare).
    def _kb_key():
        for k in _KNOWLEDGE_BASE:
            if k in low:
                return k
        return None

    arith = _first_arith()
    kb_key = _kb_key()

    if n == 0 and arith:
        return {"thought": f"First do the arithmetic part: {arith}.",
                "tool": "calculate", "args": {"expr": arith}}
    if n == 1 and kb_key:
        return {"thought": f"Now look up the fact: {kb_key}.",
                "tool": "lookup", "args": {"key": kb_key}}
    if n == 2 and kb_key:
        # Pichhle do observations (number aur fact) ko add karo.
        a = transcript[0]["observation"]
        b = transcript[1]["observation"]
        return {"thought": "Combine the calculation and the looked-up fact (add them).",
                "tool": "calculate", "args": {"expr": f"{a} + {b}"}}
    # Terminal: jo bhi last numeric observation hai usse final answer banao.
    last = transcript[-1]["observation"] if transcript else "no result"
    return {"thought": "I now have enough to answer.",
            "tool": "finish", "args": {"answer": f"Final result: {last}"}}


def run_loop(goal: str, max_iters: int = 6, tracer=None, verbose: bool = True):
    """ReAct loop runner. Returns {answer, iters, transcript, mode}.
    mode = 'live' (LLM drove the loop) ya 'scripted' (no key => deterministic policy).
    NA crash, NA hang, NA network (offline path). max_iters = HARD safety cap (Week-1 lesson)."""
    tracer = tracer or make_tracer()

    # Decide drive-mode ek baar (na ki har step): key ho to LLM, warna scripted.
    key = os.getenv("GROQ_API_KEY")
    client = model = None
    mode = "scripted"
    if key:
        client, model = get_client("groq")
        mode = "live"

    transcript = []  # list of {thought, tool, args, observation}
    answer = None

    for i in range(1, max_iters + 1):
        if verbose:
            print(f"  iter {i}/{max_iters}")

        # --- 1) THINK -------------------------------------------------------
        t0 = time.time()
        step = None
        if mode == "live":
            step = _llm_next_step(client, model, goal, transcript)
            if step is None:
                # Live fail mid-loop => is iteration se scripted par graceful switch (degrade).
                mode = "scripted"
        if step is None:
            step = _scripted_next_step(goal, transcript)

        thought = step.get("thought", "")
        tool = step.get("tool", "finish")
        args = step.get("args", {}) or {}
        tracer.span("think", "think", {"iter": i, "thought": thought, "chose_tool": tool,
                                       "args": args, "duration_ms": round((time.time() - t0) * 1000, 1)})
        if verbose:
            print(f"    THINK   : {thought}")
            print(f"    ACT     : {tool}({args})")

        # --- terminal: finish => loop khatam --------------------------------
        if tool == "finish":
            answer = args.get("answer", "(no answer provided)")
            tracer.span("final", "final", {"iter": i, "answer": answer})
            if verbose:
                print(f"    FINAL   : {answer}")
            break

        # --- 2) ACT ---------------------------------------------------------
        ta = time.time()
        observation = run_tool(tool, args)
        tracer.span("act", "act", {"iter": i, "tool": tool, "args": args,
                                   "duration_ms": round((time.time() - ta) * 1000, 1)})

        # --- 3) OBSERVE (feed back into transcript) -------------------------
        transcript.append({"thought": thought, "tool": tool, "args": args, "observation": observation})
        tracer.span("observe", "observe", {"iter": i, "observation": observation})
        if verbose:
            print(f"    OBSERVE : {observation}")
        print()  # spacing between iters
    else:
        # for-else: loop bina break ke khatam => max_iters HIT (terminal condition nahi mila).
        # Yeh wahi safety cap hai (Week-1): infinite loop / cost blowup se bachao.
        answer = (f"STOPPED: hit max_iters={max_iters} without a final answer. "
                  "(Safety cap — prevents infinite loops / cost blowup.)")
        tracer.span("final", "final", {"iter": max_iters, "answer": answer, "capped": True})
        if verbose:
            print(f"    FINAL   : {answer}")

    return {"goal": goal, "answer": answer, "iters": len(transcript), "transcript": transcript, "mode": mode}


# ===========================================================================
# ############  SINGLE-SHOT (contrast) — loop ke BINA ek hi call  ###########
# ===========================================================================
# L121 ka point dikhane ke liye: SINGLE-SHOT me LLM ko multi-step problem ek hi baar me karna
# padta (no tools, no observation feedback) -> aksar arithmetic/lookup galti. Key na ho to hum
# ise SKIP karke ek note dete (live call nahi karte) — phir bhi contrast clear rehta.
def single_shot(goal: str) -> str:
    """Contrast: ek hi LLM call, no loop, no tools. Key na ho => templated note (no network)."""
    if not os.getenv("GROQ_API_KEY"):
        return ("(SINGLE-SHOT skipped — no GROQ_API_KEY. Concept: ek hi call me LLM ko poora "
                "multi-step problem 'head me' karna padta -> tools/observation ke bina aksar "
                "galti. LOOP isse fix karta: ek-ek step + real tool output feedback.)")
    client, model = get_client("groq")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": goal + " Answer with just the final number."}],
            max_tokens=100, temperature=0.0,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"(single-shot live call failed: {type(e).__name__}: {e})"


# ===========================================================================
# ############  MANAGED PATH — BedrockAgentCoreRunner STUB (L118/L120)  #####
# ===========================================================================
# Yeh dikhata hai ki YEHI loop managed AgentCore runtime par kaise map hota. boto3 +
# bedrock-agentcore LAZY import hote (is env me dono NAHI). Missing/no-ARN => clean Hinglish
# note + LOCAL fallback (loop yahin chalao). Yeh hi L117 ka core: SAME loop, alag deployment.

def loop_agent_entrypoint(payload: dict) -> dict:
    """L120 ka `@app.entrypoint def invoke(payload)` shape. Managed runtime is function ko
    HTTP `/invocations` ke peeche call karta. Local me hum ise seedha bula sakte (same code)."""
    goal = payload.get("prompt", "")
    out = run_loop(goal, max_iters=6, verbose=False)
    return {"answer": out["answer"], "iters": out["iters"], "mode": out["mode"]}


class BedrockAgentCoreRunner:
    """MANAGED path STUB — dikhaata hai ki ye SAME loop AgentCore par kaise deploy/invoke hota
    (L118 services + L120 configure/launch/invoke). boto3 / bedrock-agentcore LAZY: is env me
    dono missing => `invoke()` clean note ke saath LOCAL fallback (loop_agent_entrypoint) chalata.
    KEY teaching (L117): code SAME hai — sirf RUNTIME (managed vs custom) badalta hai."""

    name = "bedrock-agentcore"

    def __init__(self, agent_arn=None, region=None):
        self.agent_arn = agent_arn or os.getenv("AGENTCORE_AGENT_ARN")
        self.region = region or os.getenv("AWS_REGION", "us-west-2")  # Code Interpreter us-west-2 (L122)

    def invoke(self, prompt: str) -> dict:
        """Managed invoke try karo (LAZY boto3). ARN/boto3/creds missing => LOCAL fallback.
        NEVER crash/hang/network — wahi graceful-degrade jo poore course me chala."""
        if not self.agent_arn:
            print("[INFO] AGENTCORE_AGENT_ARN not set => agent abhi AWS par deployed nahi.")
            print("[INFO] => LOCAL fallback: wahi loop yahin chalata hoon (managed=custom, same code).")
            return loop_agent_entrypoint({"prompt": prompt})
        try:
            import boto3  # noqa: F401  (LAZY — is env me missing => fallback)
        except ImportError as e:
            print(f"[INFO] boto3 missing ({e}) => AgentCore runtime use nahi ho sakta.")
            print("[INFO] => LOCAL fallback: wahi loop yahin chalata hoon (offline, $0).")
            return loop_agent_entrypoint({"prompt": prompt})
        # *** REAL managed invoke (sirf reference — is env me pahunchega hi nahi) ***
        # L120: `agentcore configure -e looper.py` + `agentcore launch` ne agent deploy kiya;
        # CLI ke neeche yeh boto3 bedrock-agentcore-control / runtime call hota:
        #   rt = boto3.client("bedrock-agentcore", region_name=self.region)
        #   resp = rt.invoke_agent_runtime(agentRuntimeArn=self.agent_arn,
        #                                  payload=json.dumps({"prompt": prompt}).encode())
        #   return json.loads(resp["response"].read())
        raise RuntimeError("AgentCore invoke is reference-only in this offline lab.")


# ===========================================================================
# SELF-DEMO — `uv run <file>` (no args). No key/boto3/AWS/langfuse => EXIT 0.
# ===========================================================================
# Shape: ek baked-in multi-step task par loop chalao (calc -> lookup -> combine -> finish),
# har think->act->observe step + spans + final answer print karo. Phir single-shot contrast,
# platform-vs-custom framing, sandbox-risk note, aur course-wrap reflection. Exit 0.
DEMO_TASK = ("What is 12.5 * 8, then add the population-millions of india? "
             "Give the final number.")


def run_self_demo():
    print("\n" + "#" * 74)
    print("#  LAB 6 SELF-DEMO — Bedrock AgentCore + loop-based reasoning agent (FINALE)")
    print("#  (no key / no boto3 / no AWS / no langfuse bhi OK — exit 0)")
    print("#" * 74 + "\n")

    tracer = make_tracer()

    # --- Setup banner -------------------------------------------------------
    print("=" * 74)
    print("SETUP  (offline-first; managed path = lazy boto3 jab configured)")
    print("=" * 74)
    print(f"tracer          = {tracer.name}  (Langfuse keys set ho to woh; warna local JSON spans)")
    print(f"tools           = {[t for t in TOOLS if t != 'finish']} + finish (terminal)")
    print(f"drive-mode      = {'live LLM' if os.getenv('GROQ_API_KEY') else 'scripted (no GROQ_API_KEY)'}")
    print(f"max_iters cap   = 6  (Week-1 safety lesson — infinite-loop / cost brake)")
    print()

    # --- 1) THE LOOP on the baked-in task ----------------------------------
    print("=" * 74)
    print("LOOP-BASED REASONING  (ReAct: think -> act -> observe -> repeat)  [L121]")
    print("=" * 74)
    print(f"TASK: {DEMO_TASK}")
    print("(har step ek SPAN emit karta — yehi 'traces' jisme L122 me Ed ne retries pakde)\n")
    out = run_loop(DEMO_TASK, max_iters=6, tracer=tracer, verbose=True)
    print(f"RESULT  -> answer={out['answer']!r}  iters={out['iters']}  mode={out['mode']}")
    print()

    # --- 2) SINGLE-SHOT contrast -------------------------------------------
    print("=" * 74)
    print("LOOP vs SINGLE-SHOT  (kyun loop chahiye)  [L121]")
    print("=" * 74)
    print("SINGLE-SHOT (no tools, no feedback) — ek hi call me poora multi-step:")
    print(f"    {single_shot(DEMO_TASK)}")
    print("LOOP me LLM sirf AGLA step sochta + REAL tool output (observation) wapas aata =>")
    print("multi-step problems reliably solve hote (calc -> lookup -> combine). Yeh hi 'agentic'.")
    print()

    # --- 3) MANAGED (AgentCore) vs CUSTOM framing --------------------------
    print("=" * 74)
    print("AGENT PLATFORM (Bedrock AgentCore) vs CUSTOM (Lambda/containers)  [L117/L118]")
    print("=" * 74)
    runner = BedrockAgentCoreRunner()  # ARN unset => local fallback demo (managed=custom, same code)
    managed_out = runner.invoke(DEMO_TASK)
    print(f"    runner.invoke(...) -> {managed_out}")
    print()
    print("  AgentCore (MANAGED) = 5 services + 2 tools umbrella:")
    print("    Runtime (deploy/run) | Identity (IAM least-priv) | Memory (short+long) |")
    print("    Gateway (tools via MCP) | Observability (built-in traces) + Browser & Code-Interpreter tools.")
    print("    `agentcore configure -e looper.py` + `agentcore launch` -> minutes me AWS par live (L120).")
    print("    PROS: killer time-to-market, batteries-included (Vercel/Heroku DX).")
    print("    CONS: kam flexibility, vendor lock-in, sab abhi naya (kai = monetization strategy).")
    print()
    print("  CUSTOM (course wala) = Lambda + ECR + Terraform + fine-grained IAM/scaling/observability.")
    print("    Slow setup par FULL control + portability. Enterprise prod AAJ BHI mostly custom;")
    print("    platforms startups/experiments ke liye. KEY: SAME loop dono jagah — sirf deployment alag.")
    print()

    # --- 4) Code-execution sandbox risk -----------------------------------
    print("=" * 74)
    print("CODE-EXECUTION TOOL — SANDBOXING RISK  [L118/L122]")
    print("=" * 74)
    demo_code = "import os; os.system('echo pwned')  # <- untrusted LLM-generated code"
    print("Agar agent code-exec maange, hum NEVER apne process me exec/eval karte. Demo:")
    print(f"    mock_execute_python({demo_code!r})")
    print(f"    -> {mock_execute_python(demo_code)}")
    print("Real AgentCore Code Interpreter (us-west-2) ise ek ISOLATED Docker sandbox me chalata.")
    print("Lesson: LLM-generated code UNTRUSTED hai — managed sandbox use karo, kabhi inline exec mat karo.")
    print()
    # NOTE: calculator bhi isi spirit me AST-based hai (NO eval) — ek aur RCE-proof tool.
    print(f"    (calculator bhi safe hai: calculate('2 ** 10') = {calculate('2 ** 10')}; "
          f"eval-injection block: {calculate('__import__(\"os\").system(\"x\")')[:46]}...)")
    print()

    # --- 5) Course wrap reflection ----------------------------------------
    print("=" * 74)
    print("COURSE WRAP REFLECTION  [L123]")
    print("=" * 74)
    print("- Production AI ka 60-80% = traditional cloud platform engineering (IAM, Docker,")
    print("  Terraform, Lambda, S3 — 'biology of AWS'). AI flavor upar weave hota hai.")
    print("- W1 Vercel/App Runner -> W2 serverless+Terraform+CI/CD -> W3 multi-cloud+data ->")
    print("  W4 multi-agent + observability + AgentCore (yeh loop agent = grand finale).")
    print("- Final assignment (Ed): jaake kuch PRODUCTION-grade deploy karo. Loop agent ko")
    print("  `looper.py` me daalo, `agentcore launch`, aur live AWS par invoke karo.")
    print()

    print("#" * 74)
    print("#  LAB 6 complete. ReAct loop (think->act->observe, max-iters capped); safe AST calc +")
    print("#  describe-only code-exec + lookup; managed AgentCore stub vs custom (same loop);")
    print("#  spans for observability; key/boto3/langfuse/AWS na ho to graceful degrade, exit 0.")
    print("#" * 74 + "\n")

    raise SystemExit(0)


# ===========================================================================
# MAIN — default self-demo; --ask "<task>" => ek hi task ka pura loop.
# ===========================================================================
if __name__ == "__main__":
    if "--ask" in sys.argv:
        idx = sys.argv.index("--ask")
        task = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else DEMO_TASK
        print("\n" + "=" * 74)
        print(f"ASK: {task}")
        print("=" * 74)
        result = run_loop(task, max_iters=6, verbose=True)
        print(f"[answer] {result['answer']}")
        print(f"[mode] {result['mode']}  [iters] {result['iters']}")
        raise SystemExit(0)
    else:
        run_self_demo()
