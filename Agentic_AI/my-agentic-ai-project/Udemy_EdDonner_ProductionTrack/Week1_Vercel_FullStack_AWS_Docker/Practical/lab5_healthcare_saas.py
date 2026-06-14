"""
LAB 5 — Week-1 PROJECT: "Healthcare info AI SaaS"  (the deployable BLUE-tile project)
=====================================================================================
Lecture mapping: Ed Donner — "AI Engineer Production Track", Week 1 · Day 4,
                 L19 (first commercial AI app) -> L20 (FastAPI + structured prompts)
                 -> L21 (deploy to Vercel) -> L22 (production SaaS + streaming).

Ed jo dikhata hai wo ek "doctor consultation assistant" (notes -> summary/email) tha,
jo Markdown headings me reply karta tha. Ed khud bolta hai (L20): "Agentic course wale
jaante hain ki BEHTAR tareeka STRUCTURED OUTPUTS hota — LLM se ek schema ke hisaab se
JSON return karwana." Yeh lab wahi RECOMMENDED upgrade hai: ek consumer-facing
"general health INFO" SaaS jo ek Pydantic-typed structured response deta hai — par
ek SUPER-STRONG SAFETY GUARDRAIL ke saath (yeh medical advice NAHI hai).

KYA SEEKHENGE (concepts, basic -> advanced):
- STRUCTURED PROMPTING for a production SaaS: LLM ko ek exact JSON schema bharne ko
  bolna (summary / possible_general_causes / self_care_tips / red_flags / disclaimer),
  Markdown-heading parsing ke fragile tarike ke bajaye.
- DEFENSIVE PARSING: LLM kabhi-kabhi extra text / ```json fences / tooti JSON deta hai.
  Hum try-structured -> fallback-wrap karte hain, taaki endpoint NEVER 500 ho.
- DETERMINISTIC GUARDRAIL: safety disclaimer ko KABHI LLM par depend NAHI karna. Wo ek
  Python constant hai jo HAR response me forcibly inject hoti hai — chaahe LLM kuch bhi
  bole, chaahe LLM call fail ho jaaye. (Yeh L21 ki "HIPAA badge" wali honest warning ka
  production-grade version hai: compliance/safety ko code me HARD-WIRE karo, prompt me
  "umeed" mat karo.)
- FastAPI + Pydantic request/response modeling (L20 ka core), POST /assess + GET /health.
- COMMERCIAL/MONETIZATION angle (L19/L22 "springboard"): yeh ek chargeable SaaS shape hai
  (Clerk-gated /assess, subscription tiers), AI yahaan "side-note" hai — asli skill clean
  stateless endpoint design + deployment hai (L22 "AI is a side-note").

KAISE CHALANA (how to run):
    # 1) Default = built-in TestClient self-demo (NO server, NO browser). Apne hi routes
    #    ko call karke results PRINT karta hai, phir EXIT 0. API key ke bina bhi chalega.
    uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab5_healthcare_saas.py

    # 2) Real server (browser / curl / Postman ke liye) — uvicorn launch karta hai:
    uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab5_healthcare_saas.py --serve
    #    Phir: open http://127.0.0.1:8000/health   (aur /docs par Swagger UI)
    #    curl -X POST http://127.0.0.1:8000/assess \
    #         -H "Content-Type: application/json" \
    #         -d '{"symptoms":"mild sore throat and runny nose","age":30,"duration":"2 days"}'

Setup: .env me GROQ_API_KEY (default provider=groq => free + fast + OpenAI-compatible).
       Key MISSING/empty ho to bhi sab chalega — self-demo live LLM ko skip kar deta hai.

COST:
- Is lab ko LOCALLY chalana = $0. /health bilkul free hai. /assess ka structured LLM call
  Groq par default => free tier (zero $). Provider "gemini" bhi free-tier friendly hai.
- Cloud DEPLOY (runbook angle, L21/L22): Vercel Hobby tier = $0 to host this FastAPI
  function (cold-start serverless). Asli laagat sirf LLM tokens (Groq free / OpenAI pe
  ~paise-per-1k-tokens) + agar Clerk billing/Stripe lagao to unke fees. Day-5 me AWS
  App Runner pe same app ~ a few $/month (always-on container) — Vercel (PaaS, $0 start)
  vs AWS (IaaS, paise lagte hain par industrial scale) ka wahi trade-off jo Ed compare
  karwata hai.
"""

import os
import sys
import json
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from pydantic import BaseModel, Field
from fastapi import FastAPI
from fastapi.testclient import TestClient

# .env load. override=True => shell me purani value ho to .env wali jeet jayegi
# (Ed Donner isi convention ko follow karta hai poore course me).
load_dotenv(override=True)


# ===========================================================================
# get_client — provider ke hisaab se (client, model) return karta hai.
# Groq + Gemini dono OpenAI-compatible hain (bas base_url alag). File ko
# SELF-CONTAINED rakhne ke liye helper yahin inline define kiya hai (course style).
# ===========================================================================
def get_client(provider: str = "groq"):
    """(client, model) return karta hai. Default groq => zero cost, fast, OpenAI-compatible."""
    if provider == "groq":
        return OpenAI(base_url="https://api.groq.com/openai/v1",
                      api_key=os.getenv("GROQ_API_KEY") or "placeholder"), "llama-3.3-70b-versatile"
    if provider == "gemini":
        return OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                      api_key=os.getenv("GOOGLE_API_KEY") or "placeholder"), "gemini-2.5-flash"
    raise ValueError(f"Unknown provider: {provider}")


# ===========================================================================
# THE DETERMINISTIC GUARDRAIL — sabse important constant of this lab.
#
# WHY a Python constant (not the LLM)?
#   Ek health-info SaaS me sabse bada LEGAL + ETHICAL risk yeh hai ki user isse
#   "diagnosis"/"medical advice" samajh le. Agar hum disclaimer ko LLM ke output
#   par chhod den, to: (a) LLM kabhi-kabhi disclaimer drop kar dega, (b) prompt
#   injection ("ignore previous instructions") se attacker use hata sakta hai,
#   (c) model update hone par behaviour silently badal sakta hai.
#   => Safety-critical text KABHI probabilistic component (LLM) par depend NAHI
#      hona chahiye. Hum ise har response me FORCIBLY inject karte hain — chaahe
#      LLM kuch bhi bole, chaahe LLM call hi fail ho jaaye. Yeh exactly L21 ki
#      "HIPAA badge demo-only" warning ka production-grade fix hai: compliance/
#      safety ko CODE me hard-wire karo, prompt me "umeed" mat karo.
# ===========================================================================
SAFETY_DISCLAIMER = (
    "This is GENERAL HEALTH INFORMATION ONLY and is NOT medical advice, diagnosis, "
    "or treatment. It is not a substitute for a consultation with a licensed "
    "healthcare professional. Always consult a qualified doctor about your symptoms. "
    "If you experience any red-flag / emergency symptoms (e.g. difficulty breathing, "
    "chest pain, severe bleeding, sudden weakness, confusion, or thoughts of self-harm), "
    "call your local emergency services immediately."
)

# Ek baseline red-flag jo HAMESHA list me hoga — bhale LLM kuch na de. Yeh bhi
# deterministic safety hai: emergency-escalation advice LLM par depend nahi karta.
ALWAYS_RED_FLAG = (
    "Seek emergency care immediately for any severe or rapidly worsening symptoms "
    "(trouble breathing, chest pain, severe bleeding, fainting, confusion, or "
    "thoughts of self-harm)."
)


# ===========================================================================
# SYSTEM PROMPT — structured prompting (L20 ka core + L20 me Ed-recommended upgrade).
# Hum LLM ko bolte hain: sirf JSON, exact fields, aur SAFETY rules. Disclaimer ke
# liye bhi bolte hain — BUT hum LLM par bharosa NAHI karte (neeche forcibly override).
# "Belt and suspenders": prompt me bhi maango AUR code me bhi enforce karo.
# ===========================================================================
SYSTEM_PROMPT = (
    "You are a careful, conservative GENERAL HEALTH INFORMATION assistant for a "
    "consumer wellness app. You DO NOT diagnose, you DO NOT prescribe, and you DO NOT "
    "give personalized medical advice. You provide only safe, general, educational "
    "information and you ALWAYS encourage consulting a licensed healthcare professional.\n\n"
    "Given a user's described symptoms (and optional age/duration), respond with a "
    "STRICT JSON object and NOTHING else (no markdown, no code fences, no commentary). "
    "The JSON MUST have EXACTLY these keys:\n"
    '  "summary": a 1-2 sentence neutral, non-alarming restatement (string)\n'
    '  "possible_general_causes": a list of common, GENERAL non-diagnostic possibilities (list of strings)\n'
    '  "self_care_tips": a list of safe, general self-care suggestions (list of strings)\n'
    '  "red_flags_seek_doctor": a list of warning signs that warrant prompt professional/emergency care (list of strings)\n'
    '  "disclaimer": a short safety disclaimer reminding this is not medical advice (string)\n\n'
    "Rules: never state a definitive diagnosis; never recommend specific prescription "
    "drugs or dosages; keep everything general and educational; if symptoms sound "
    "serious, strongly emphasize seeking professional/emergency care. Output JSON only."
)


# ===========================================================================
# Pydantic MODELS — request + response ka typed schema (L20: FastAPI ka killer feature).
# Request body POST hote hi FastAPI ise validate + populate kar deta hai (invalid =>
# automatic 422, no manual request.json()). Response model API ka CONTRACT hai —
# frontend isi shape par bharosa kar sakta hai, isiliye structured > Markdown.
# ===========================================================================
class AssessRequest(BaseModel):
    """POST /assess ka request body. age aur duration OPTIONAL hain (None default)."""
    symptoms: str = Field(..., description="User-described symptoms, free text.")
    age: Optional[int] = Field(None, description="Optional age in years.")
    duration: Optional[str] = Field(None, description="Optional duration, e.g. '2 days'.")


class AssessResponse(BaseModel):
    """POST /assess ka structured response. disclaimer HAMESHA populate hoti hai
    (deterministic — neeche server LLM output ko override karta hai)."""
    summary: str
    possible_general_causes: List[str]
    self_care_tips: List[str]
    red_flags_seek_doctor: List[str]
    disclaimer: str


# ===========================================================================
# parse_llm_to_response — DEFENSIVE PARSING.
# LLM "JSON only" bola tha, par real life me wo de sakta hai:
#   - clean JSON  (best case)
#   - ```json ... ``` fenced JSON  (common)
#   - JSON + leading/trailing prose  (annoying)
#   - bilkul plain text  (worst case)
# Production endpoint ko in sabme CRASH nahi hona chahiye. Strategy: try structured
# JSON -> agar fail, plain text ko summary me WRAP kar do. End me chaahe kuch bhi
# ho, disclaimer + ek baseline red-flag FORCIBLY set karte hain.
# ===========================================================================
def parse_llm_to_response(raw_text: str) -> AssessResponse:
    """LLM ke raw text ko AssessResponse me convert karo — defensively."""
    data = None
    text = (raw_text or "").strip()

    # Step 1: agar ```json ... ``` fence hai to nikal do (LLMs aksar lagaate hain).
    if text.startswith("```"):
        # pehli newline ke baad ka content lo, trailing ``` hatao.
        inner = text.split("```", 2)
        if len(inner) >= 2:
            body = inner[1]
            # "json" language tag pehli line me ho sakta hai — usse hata do.
            if body.lstrip().lower().startswith("json"):
                body = body.lstrip()[4:]
            text = body.strip()

    # Step 2: try strict JSON parse. Agar prose ke beech JSON hai, to {..} slice kar
    # ke parse try karo (best-effort).
    try:
        data = json.loads(text)
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(text[start:end + 1])
            except Exception:
                data = None

    if isinstance(data, dict):
        # Structured path: har field ko safely nikaalo, type-coerce karo.
        def as_list(v):
            if isinstance(v, list):
                return [str(x) for x in v]
            if v:
                return [str(v)]
            return []

        return AssessResponse(
            summary=str(data.get("summary") or "").strip()
                    or "General information about the described symptoms.",
            possible_general_causes=as_list(data.get("possible_general_causes")),
            self_care_tips=as_list(data.get("self_care_tips")),
            # NOTE: ALWAYS_RED_FLAG ko hamesha list me jodte hain (deterministic safety).
            red_flags_seek_doctor=as_list(data.get("red_flags_seek_doctor")) + [ALWAYS_RED_FLAG],
            disclaimer=SAFETY_DISCLAIMER,  # <-- LLM ka disclaimer IGNORE; humara fixed.
        )

    # Step 3: FALLBACK — LLM ne plain text diya. Crash mat karo: text ko summary me
    # wrap kar do, baaki fields safe-empty, par safety fields HAMESHA bhare rahein.
    return AssessResponse(
        summary=(text[:500] or "General information about the described symptoms."),
        possible_general_causes=[],
        self_care_tips=[
            "Rest, stay hydrated, and monitor how your symptoms change over time.",
        ],
        red_flags_seek_doctor=[ALWAYS_RED_FLAG],
        disclaimer=SAFETY_DISCLAIMER,
    )


# ===========================================================================
# safe_fallback_response — jab LLM call BILKUL na ho (no key) ya FAIL ho jaaye.
# Yeh proves karta hai ki SaaS ka "shape" + safety LLM ke bina bhi intact hai.
# /assess kabhi 500 nahi karega — degrade gracefully.
# ===========================================================================
def safe_fallback_response(reason: str) -> AssessResponse:
    return AssessResponse(
        summary=("We could not generate live general information right now "
                 f"({reason}). Please consult a licensed healthcare professional."),
        possible_general_causes=[],
        self_care_tips=[
            "Rest and stay hydrated.",
            "Monitor your symptoms and note any changes.",
        ],
        red_flags_seek_doctor=[ALWAYS_RED_FLAG],
        disclaimer=SAFETY_DISCLAIMER,
    )


# ===========================================================================
# run_assessment — core business logic (route se alag taaki self-demo + tests
# dono isse reuse kar saken). LLM call yahaan hota hai, defensively.
# ===========================================================================
def run_assessment(req: AssessRequest, provider: str = "groq") -> AssessResponse:
    """Structured prompt -> LLM -> defensive parse. No key / error => safe fallback.
    Lekin disclaimer + baseline red-flag HAR raaste me guaranteed milte hain."""

    # GUARDRAIL CHECK #1: key missing/empty? to LLM ko call hi mat karo. Self-demo
    # aur production dono me yeh "free, never-hangs" path deta hai.
    if not os.getenv("GROQ_API_KEY"):
        return safe_fallback_response("LLM API key not configured")

    # User prompt — typed request se context banao (age/duration optional).
    user_prompt = (
        f"Symptoms: {req.symptoms}\n"
        f"Age: {req.age if req.age is not None else 'not provided'}\n"
        f"Duration: {req.duration if req.duration else 'not provided'}\n\n"
        "Return the strict JSON object as instructed."
    )

    try:
        client, model = get_client(provider)
        # timeout chhota rakha => self-demo / endpoint kabhi HANG na kare.
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,  # health info => low temp, kam creative/zyada predictable.
            timeout=30,
        )
        raw = resp.choices[0].message.content
        return parse_llm_to_response(raw)
    except Exception as e:
        # Network / key / rate-limit / model issue — endpoint ko 500 nahi hone dena.
        return safe_fallback_response(f"LLM call failed: {type(e).__name__}")


# ===========================================================================
# FastAPI APP + ROUTES.
#   GET  /health  -> hamesha free, no LLM. Liveness/readiness probe (AWS App
#                    Runner / load balancers isi tarah health check karte hain).
#   POST /assess  -> structured health-info, AssessResponse-typed.
# ===========================================================================
app = FastAPI(
    title="Healthcare Info AI SaaS",
    description=("General health INFORMATION only — NOT medical advice. "
                 "Week-1 Day-4 deployable project (Ed Donner Production Track)."),
    version="1.0.0",
)


@app.get("/health")
def health():
    """Liveness check. LLM ya key ki zaroorat NAHI — yeh hamesha 200 OK dega."""
    return {"status": "ok", "service": "healthcare-info-ai-saas"}


@app.post("/assess", response_model=AssessResponse)
def assess(req: AssessRequest):
    """User ke symptoms par STRUCTURED general health info do.
    response_model=AssessResponse => FastAPI output ko validate + document karta hai
    (Swagger /docs me bhi clean schema dikhta hai). disclaimer ALWAYS present."""
    return run_assessment(req)


# ===========================================================================
# SELF-DEMO — default `uv run <file>` (no args) yahi chalata hai. Built-in
# TestClient se apne hi routes ko call karta hai (real HTTP server BAGAIR), result
# PRINT karta hai, phir EXIT 0. Yeh course ki strict convention hai: har FastAPI
# lab no-args pe demonstrable + non-hanging hona chahiye.
# ===========================================================================
def run_self_demo():
    print("\n" + "#" * 74)
    print("#  LAB 5 — Healthcare Info AI SaaS  (Week 1 · Day 4 · BLUE-tile project)")
    print("#  self-demo via FastAPI TestClient (no real server, no browser)")
    print("#" * 74 + "\n")

    client = TestClient(app)

    # --- 1) GET /health — hamesha free, hamesha 200 -------------------------
    print("=" * 74)
    print("1) GET /health  (no LLM, no key needed — always works)")
    print("=" * 74)
    r = client.get("/health")
    print(f"   HTTP {r.status_code}  ->  {r.json()}\n")

    # --- 2) Disclaimer ko upfront dikhao (deterministic, LLM-independent) ----
    print("=" * 74)
    print("2) DETERMINISTIC SAFETY DISCLAIMER (hard-wired, NOT from the LLM)")
    print("=" * 74)
    print("   " + SAFETY_DISCLAIMER.replace(". ", ".\n   "))
    print()

    # --- 3) POST /assess — key ke hisaab se do raaste -----------------------
    print("=" * 74)
    print("3) POST /assess  (structured Pydantic response)")
    print("=" * 74)

    sample = {
        "symptoms": "mild sore throat and runny nose",
        "age": 30,
        "duration": "2 days",
    }
    print(f"   Sample request body: {json.dumps(sample)}\n")

    has_key = bool(os.getenv("GROQ_API_KEY") or "placeholder")
    if not has_key:
        # NO-KEY PATH: live LLM ko skip. Response SHAPE + disclaimer dikhao taaki
        # reader ko contract samajh aaye, bina kisi key/network ke. EXIT 0 guaranteed.
        print("   [LLM SKIPPED] GROQ_API_KEY missing/empty hai — live call skip "
              "kar rahe hain.")
        print("   Niche response ka SHAPE (deterministic fallback) dikha rahe hain:\n")
        resp_obj = safe_fallback_response("LLM API key not configured")
    else:
        # WITH-KEY PATH: ek asli structured /assess call (route ke through).
        print("   [LLM LIVE] GROQ_API_KEY mila — ek sample /assess call kar rahe hain "
              "(provider=groq, free)...\n")
        http = client.post("/assess", json=sample)
        print(f"   HTTP {http.status_code}")
        # Response ko AssessResponse me wapas load karke pretty-print karte hain.
        resp_obj = AssessResponse(**http.json())

    # Structured response ko field-by-field print karo (yahi "SHAPE" hai).
    print("   --- AssessResponse (structured) ---")
    print(f"   summary                 : {resp_obj.summary}")
    print(f"   possible_general_causes : {resp_obj.possible_general_causes}")
    print(f"   self_care_tips          : {resp_obj.self_care_tips}")
    print(f"   red_flags_seek_doctor   : {resp_obj.red_flags_seek_doctor}")
    print(f"   disclaimer (ALWAYS set) : {resp_obj.disclaimer[:80]}...")
    print()

    # --- 4) Lesson recap ----------------------------------------------------
    print("=" * 74)
    print("AHA POINTS:")
    print("  - STRUCTURED prompting -> typed JSON contract (Markdown parsing se behtar).")
    print("  - DEFENSIVE parsing -> /assess kabhi 500 nahi karta (key/JSON/network fail).")
    print("  - DISCLAIMER deterministic hai: LLM par DEPEND nahi karta — safety-critical "
          "text ko code me hard-wire karo.")
    print("  - COMMERCIAL angle: yeh ek chargeable SaaS shape hai; AI 'side-note' hai, "
          "asli skill clean endpoint + deploy hai (L22).")
    print("=" * 74 + "\n")

    print("#" * 74)
    print("#  LAB 5 self-demo complete.  --serve se real uvicorn server bhi chala sakte ho.")
    print("#" * 74 + "\n")


# ===========================================================================
# MAIN — `--serve` => real uvicorn; warna => self-demo. Dono EXIT 0.
# ===========================================================================
if __name__ == "__main__":
    if "--serve" in sys.argv:
        # Real server: browser / curl / /docs (Swagger) ke liye.
        import uvicorn
        print("Starting uvicorn on http://127.0.0.1:8000  (Ctrl+C to stop)")
        print("Try:  GET /health   |   POST /assess   |   Swagger UI at /docs")
        uvicorn.run(app, host="127.0.0.1", port=8000)
    else:
        # Default: self-contained demo. Never hangs, never crashes, exits 0.
        try:
            run_self_demo()
        except Exception as e:
            # Last-resort guard: koi unexpected error bhi crash na banaye.
            print(f"\n[SELF-DEMO ERROR] {type(e).__name__}: {e}")
            print("Yeh demo error hai — /health aur deterministic disclaimer fir bhi valid hain.")
        raise SystemExit(0)
