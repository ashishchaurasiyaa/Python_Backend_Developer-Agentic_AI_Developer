"""
LAB 2 — LLM behind a PRODUCTION API + cost management
=====================================================
Title: Ek LLM call ko ek clean, deployable FastAPI endpoint ke peeche wrap karna,
       aur usi ke saath API COST ko control me rakhna.

KYA SEEKHENGE (what concepts):
- SERVER-SIDE LLM PROXY pattern: browser kabhi LLM ko directly call nahi karta
  (warna API key leak ho jaaye). Request hamare FastAPI backend par aati hai;
  backend secret key ke saath LLM call karta hai aur ek SAAF, controlled JSON
  response return karta hai. Yahi har production GenAI app ki neenv hai (L06 ka
  "BFF / API-key-on-the-server" point).
- Pydantic REQUEST body se input validation (garbage-in => 422, crash nahi).
- response.usage se TOKEN counts capture karna => yahi cost ka real metric hai.
- COST MANAGEMENT: token-based pricing, max_tokens se cost cap, model tiering
  (gpt-4o-mini vs gpt-4o, ya groq free), aur health/observability endpoints.
- FastAPI app ko DO tareeke se chalana: self-demo (TestClient) ya real server
  (uvicorn) — bilkul wahi pattern jo production deploy (Vercel/App Runner) me
  use hota hai.

KAISE CHALANA (how to run) — CWD = repo root:
    # 1) Default: built-in self-demo (TestClient apne hi routes ko call karta hai)
    uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab2_llm_api_cost.py

    # 2) Real server (browser/curl ke liye) — http://127.0.0.1:8000/docs khol ke try karo
    uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab2_llm_api_cost.py --serve

Setup: .env me GROQ_API_KEY ho to /generate live LLM call karega (default provider
= groq => free + fast + OpenAI-compatible). Key na ho to /generate friendly message
deta hai aur self-demo request/response SHAPE dikha ke EXIT 0 karta hai (crash nahi).
/health aur /models bina kisi key ke bhi chalte hain.

LECTURE MAPPING: Ed Donner "AI Engineer Production Track", Week 1 · Day 1 -> Day 2.
  L06 = Deploy first live AI app (OpenAI call backend ke peeche) ; usi LLM call ko
        ab ek production-shaped API banaya.
  L07 = Managing API costs (token pricing, alerts/quotas, "spend = teri zimmedari")
        => yahan max_tokens cap + model tiering + usage tracking se cost discipline.
  L08 = Course expectations / wrap (Day 1 done = 5%).

COST: Is lab ko LOCALLY chalana = $0. Default provider groq ka free tier use hota
  hai (no upfront deposit). Bina API key ke bhi self-demo, /health, /models chalte
  hain => zero cost, zero crash. CLOUD me yeh wahi service hai jo aage runbook me
  Vercel / AWS App Runner par deploy hogi: wahan OpenAI gpt-4o-mini par har call
  ek cent ke fraction me (token-based) lagti hai, aur AWS compute par chhota
  charge — Ed ka pura course estimate ~$5-$10 (zyaadatar free). Production me
  hard cap nahi hota (sirf alerts/quotas), isliye max_tokens + sasta model =
  pehli line of defense.
"""

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

# .env load karte hain. override=True => agar shell me purani value set hai to
# .env wali jeet jayegi (Ed Donner isi convention ko follow karta hai).
load_dotenv(override=True)


# ---------------------------------------------------------------------------
# get_client: provider ke hisaab se (client, model_name) return karta hai.
# Groq aur Gemini OpenAI-compatible hain — bas base_url alag hota hai. Isiliye
# wahi ek `openai` library teeno providers ko call kar leti hai (L06 ka point:
# `openai` library koi LLM code nahi rakhti, sirf ek HTTP wrapper hai).
# File ko SELF-CONTAINED rakhne ke liye helper yahin inline rakha hai.
# ---------------------------------------------------------------------------
def get_client(provider: str = "groq"):
    """(client, model) return karta hai. Default groq => zero cost, fast, OpenAI-compatible."""
    # NOTE: `OpenAI(...)` constructor key MISSING hone par turant OpenAIError
    # ("Missing credentials") raise karta hai — bhale hi koi network call na ho.
    # Hum client ko sirf model-name ke liye bhi build karte hain (e.g. /models),
    # isliye `or "placeholder"` daala hai: construction kabhi crash na kare. Yeh
    # bilkul safe hai — placeholder se LIVE call hone par hi auth fail hoga, aur
    # /generate us se PEHLE hi key check karke gracefully degrade kar deta hai.
    if provider == "groq":
        return OpenAI(base_url="https://api.groq.com/openai/v1",
                      api_key=os.getenv("GROQ_API_KEY") or "placeholder"), "llama-3.3-70b-versatile"
    if provider == "gemini":
        return OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                      api_key=os.getenv("GOOGLE_API_KEY") or "placeholder"), "gemini-2.5-flash"
    raise ValueError(f"Unknown provider: {provider}")


# Default provider ek hi jagah define — taaki /models aur /generate dono consistent
# rahein. Production me ye config (env var) se aata, abhi hardcoded for clarity.
PROVIDER = "groq"


# ===========================================================================
# ############################  API COST MANAGEMENT  ########################
# ===========================================================================
# Yeh block sirf comment hai par is lab ka DIL hai (L07 ka core lesson).
#
# 1) TOKEN-BASED PRICING: LLM providers per-TOKEN charge karte hain, per-request
#    nahi. Token ~ shabd ka tukda (roughly 1 token ~= 4 English chars). Bill do
#    hisson me banta hai:
#       - prompt_tokens     -> jo humne bheja (input)        -> aksar sasta rate
#       - completion_tokens -> jo model ne generate kiya (output) -> aksar mehenga rate
#       - total_tokens      -> dono ka sum (yahi bill drive karta hai)
#    Isiliye hum response.usage ko capture karke API me wapas dete hain —
#    "jo measure nahi hota, wo control nahi hota."
#
# 2) max_tokens SE COST CAP: output tokens hi sabse mehenge hote hain. max_tokens
#    OUTPUT par ek HARD UPPER BOUND lagata hai => ek single call ki worst-case cost
#    bounded ho jaati hai. Bina cap ke ek runaway/verbose response bill blow kar
#    sakta hai. (L07: cloud me hard cap nahi hota, isliye app-level caps zaroori.)
#
# 3) MODEL TIERING: har request ko sabse mehenge model ki zaroorat nahi.
#       - gpt-4o-mini  -> sasta, fast; classify/extract/summarize jaise kaam ke liye
#                         kaafi (90% production traffic isi par chal sakta hai).
#       - gpt-4o       -> mehenga, sirf hard reasoning ke liye reserve karo.
#       - groq free    -> dev/local me $0 (llama-3.3-70b), isliye yahan DEFAULT.
#    Rule: "sabse sasta model jo kaam de raha hai, wahi use karo" — phir zaroorat
#    par hi upgrade. Yeh single sabse bada cost lever hai.
#
# 4) GROQ FREE-TIER (yahan): default provider groq hai jiska free tier hai (no $5
#    upfront), isliye LOCAL runs ka cost $0. Production me OpenAI/AWS par jaake
#    yahi knobs (max_tokens + model tier + usage logging) cost ko kaabu me rakhte
#    hain — saath me billing alerts/budgets (Day 5 par AWS Budgets).
# ===========================================================================


# ---------------------------------------------------------------------------
# Pydantic REQUEST model: yahi "production-grade input validation" hai.
# Client jo JSON bhejega usse FastAPI is shape me validate karega; galat type/
# missing field par khud 422 return karega — humara code crash nahi hoga.
# ---------------------------------------------------------------------------
class GenerateRequest(BaseModel):
    # prompt required hai. min_length=1 => empty string reject (garbage-in guard).
    prompt: str = Field(..., min_length=1, description="User ka prompt jo LLM ko jaayega")
    # max_tokens ka DEFAULT 256 — cost cap ka primary knob. ge/le se sane bounds
    # taaki koi 1_000_000 maang ke bill na blow kar de (L07 cost discipline).
    max_tokens: int = Field(default=256, ge=1, le=4096,
                            description="Output tokens ki upper limit => cost cap")


# ---------------------------------------------------------------------------
# FastAPI app. title/description Swagger UI (/docs) par dikhte hain — yeh wahi
# self-documenting API hai jo production me handover/debugging easy karta hai.
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Lab 2 — LLM behind a production API",
    description="Ek LLM call ko clean endpoint ke peeche, cost-aware tareeke se.",
    version="1.0.0",
)


# ===========================================================================
# GET /health  -> liveness/readiness check. KOI KEY NAHI chahiye.
# ===========================================================================
# Yeh production me load balancer / App Runner / Kubernetes ke liye CRITICAL hai:
# platform is endpoint ko poll karke decide karta hai ki container "healthy" hai.
# Isliye ye LLM ko call NAHI karta (warna har health-check par paisa lagta + slow).
# llm_configured sirf batata hai ki key set hai ya nahi — bina key reveal kiye.
@app.get("/health")
def health():
    """App zinda hai? Haan. Aur LLM key configured hai ya nahi — bina key dikhaye."""
    key = os.getenv("GROQ_API_KEY")
    return {
        "status": "ok",
        "provider": PROVIDER,
        # bool() => sirf True/False expose hota hai, kabhi actual key nahi.
        "llm_configured": bool(key),
    }


# ===========================================================================
# GET /models -> configured model + cost-control guidance. KOI KEY NAHI chahiye.
# ===========================================================================
@app.get("/models")
def models():
    """Configured model dikhata hai + sasta-model chunne ka chhota Hinglish note."""
    # Note: client banane ki zaroorat nahi — sirf model name chahiye, isliye hum
    # provider->model mapping se hi pull kar lete hain (no network, no cost).
    _, model = get_client(PROVIDER)
    return {
        "provider": PROVIDER,
        "model": model,
        # Hinglish cost-control note (L07): har use-case par mehenga model mat thoko.
        "cost_note": (
            "Cost control ka asli lever = MODEL TIERING. Sabse sasta model jo kaam "
            "kar de wahi use karo. gpt-4o-mini (sasta, fast) bohot saare kaam — "
            "classify/extract/summarize — ke liye kaafi hai; gpt-4o (mehenga) sirf "
            "hard reasoning ke liye reserve karo. Local/dev me groq free-tier "
            "(llama-3.3-70b) use karo => $0 cost. Saath me max_tokens cap lagao "
            "taaki output (sabse mehenga part) bounded rahe."
        ),
        "tiers": {
            "cheap_default": "gpt-4o-mini (ya groq llama-3.3-70b free)",
            "expensive_when_needed": "gpt-4o (sirf hard reasoning)",
        },
    }


# ===========================================================================
# POST /generate -> asli LLM call, cost-aware, graceful-degrade ke saath.
# ===========================================================================
@app.post("/generate")
def generate(req: GenerateRequest):
    """Prompt -> LLM output + token usage + cost note. Bina key ke crash nahi karta."""
    # --- GRACEFUL DEGRADATION (mandatory) -------------------------------
    # Key missing/empty? To LIVE call mat karo. 200 ke saath ek clear message do
    # aur request/response SHAPE dikha do — taaki API contract phir bhi samajh aaye
    # aur koi 500/hang na ho. (Yeh production resilience + L07 cost-safety dono hai.)
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return {
            "output": None,
            "model": get_client(PROVIDER)[1],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "est_cost_note": (
                "GROQ_API_KEY missing => live call skip. Local cost $0. Key set "
                "karne par yahan real output + token usage aayega."
            ),
            "note": "key missing, skipping live call",
        }

    # --- LIVE CALL ------------------------------------------------------
    client, model = get_client(PROVIDER)
    messages = [{"role": "user", "content": req.prompt}]

    # max_tokens=req.max_tokens => OUTPUT par hard cap (cost ka primary brake).
    # Yeh wahi chat-completions pattern hai jo L06 me dekha (server-side proxy).
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=req.max_tokens,
    )

    # response.usage => yahi cost ka real-world metric hai. Defensive .get/getattr
    # use kar rahe hain kyunki kuch providers usage ko None bhi de sakte hain.
    usage = getattr(response, "usage", None)
    usage_dict = {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }

    return {
        "output": response.choices[0].message.content,
        "model": model,
        "usage": usage_dict,
        # est_cost_note: groq free hai => $0; par production me yahi total_tokens
        # ko per-token rate se multiply karke ek est cost log kiya jaata.
        "est_cost_note": (
            f"{usage_dict['total_tokens']} total tokens use hue. Provider=groq "
            f"(free-tier) => est cost ~$0. OpenAI gpt-4o-mini par yeh ek cent ke "
            f"fraction me aata; max_tokens cap output ko bounded rakhta hai."
        ),
    }


# ===========================================================================
# SELF-DEMO — `uv run <file>` (no args) yahan aata hai.
# TestClient app ko in-process call karta hai (real network/server nahi) — yeh
# wahi tarika hai jisse production me API ka contract test kiya jaata hai.
# ===========================================================================
def run_self_demo():
    """TestClient se apne hi routes hit karke results print karo, phir exit 0."""
    print("\n" + "#" * 72)
    print(f"#  LAB 2 SELF-DEMO — LLM behind a production API   (provider = {PROVIDER})")
    print("#" * 72 + "\n")

    # TestClient app ko bina uvicorn/network ke chala leta hai.
    client = TestClient(app)

    # --- /health (no key needed) ---------------------------------------
    print("=" * 72)
    print("GET /health  (no API key needed)")
    print("=" * 72)
    r = client.get("/health")
    print(f"status_code = {r.status_code}")
    print(f"body        = {r.json()}\n")

    # --- /models (no key needed) ---------------------------------------
    print("=" * 72)
    print("GET /models  (no API key needed)")
    print("=" * 72)
    r = client.get("/models")
    body = r.json()
    print(f"status_code = {r.status_code}")
    print(f"provider    = {body['provider']}")
    print(f"model       = {body['model']}")
    print(f"cost_note   = {body['cost_note']}\n")

    # --- /generate -----------------------------------------------------
    print("=" * 72)
    print("POST /generate  (Pydantic body: {prompt, max_tokens})")
    print("=" * 72)
    sample = {"prompt": "In one short sentence, what is a production API gateway?",
              "max_tokens": 64}
    print(f"REQUEST shape  = {sample}")

    has_key = bool(os.getenv("GROQ_API_KEY"))
    if not has_key:
        # Key missing => clear Hinglish message + RESPONSE SHAPE dikhao, exit 0.
        print("\n[INFO] GROQ_API_KEY missing => skipping live call (local cost $0).")
        print("[INFO] key missing, skipping live call — niche response SHAPE dekho:\n")

    r = client.post("/generate", json=sample)
    print(f"status_code    = {r.status_code}")
    # json.dumps-style pretty print taaki shape saaf dikhe.
    import json
    print("RESPONSE       = " + json.dumps(r.json(), indent=2, ensure_ascii=False))
    print()

    print("#" * 72)
    print("#  LAB 2 complete. Pattern: client -> FastAPI -> LLM -> clean JSON.")
    print("#  Cost knobs dekhe: max_tokens cap + model tiering + usage tracking.")
    print("#" * 72 + "\n")

    # Hamesha clean exit 0 — chaahe key ho ya na ho.
    raise SystemExit(0)


# ===========================================================================
# MAIN — --serve diya to real uvicorn server; warna self-demo.
# ===========================================================================
if __name__ == "__main__":
    if "--serve" in sys.argv:
        # Real server: ab tum browser me http://127.0.0.1:8000/docs khol ke
        # /generate ko interactively try kar sakte ho (Swagger UI). Yeh wahi
        # uvicorn process hai jo production container me chalta hai.
        import uvicorn
        print("Server start ho raha hai -> http://127.0.0.1:8000  "
              "(docs: /docs).  Ctrl+C se rok do.")
        uvicorn.run(app, host="127.0.0.1", port=8000)
    else:
        # Default: self-contained demo. No args, (optionally) no key => exit 0.
        run_self_demo()
