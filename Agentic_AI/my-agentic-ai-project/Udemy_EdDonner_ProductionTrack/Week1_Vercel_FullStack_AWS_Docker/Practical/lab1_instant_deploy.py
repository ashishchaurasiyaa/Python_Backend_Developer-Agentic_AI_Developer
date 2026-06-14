"""
LAB 1 — "Instant production deploy" (Ed Donner Production Track, Week 1 Day 1)
=============================================================================

KYA SEEKHENGE (what we learn here):
- FASTAPI kya hai aur ek minimal "live from production" app kaise dikhta hai.
  (Ed ka Day 1 instant-gratification wala app — koi AI nahi, sirf JSON routes.)
- SERVERLESS DEPLOY on VERCEL ka matlab: tum sirf code dete ho, Vercel har
  incoming request par ek "serverless function" spin karta hai — koi VM, koi
  nginx, koi SSL setup khud nahi. Pay-per-use, auto-scale, zero idle server.
- vercel.json ka `builds` + `routes` MAPPING: ek incoming HTTP request ko
  Vercel hamare Python module (is FastAPI `app`) tak kaise pahunchata hai.
- DEPLOYMENT PROTECTION (Vercel Authentication) toggle: tumhara PEHLA deploy
  by-default PRIVATE hota hai (sirf logged-in team members dekh sakte hain).
  Public karne ke liye yeh setting OFF karni padti hai — yeh ek asli
  production security concept hai (staging ko private rakho, prod ko public).
- NO LLM is lab me — yeh sirf deployment foundation hai (L01-L03 ka core).

KAISE CHALANA (how to run) — CWD = my-agentic-ai-project:
    # 1) DEFAULT: built-in TestClient self-demo (NO server, NO browser, exit 0)
    uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab1_instant_deploy.py

    # 2) --serve: asli uvicorn server (browser/curl se test karne ke liye)
    uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab1_instant_deploy.py --serve
    # phir browser: http://127.0.0.1:8000/   (ya /health, /info, /docs)

LECTURE MAPPING:
- L01 "Instant AI Deployment: First Production App on Vercel"  -> FastAPI app,
  requirements.txt, vercel.json (builds + routes), `vercel .` deploy.
- L02 "From Zero to Live SaaS"  -> Deployment Protection / Vercel
  Authentication toggle (pehla deploy private kyun hota hai), incognito test.
- L03 "AI Concepts to Cloud DevOps"  -> 70-80% kaam DevOps hai; code "hello"
  return kare ya LLM call kare, deployment pipeline same rehti hai. Isiliye
  yeh foundational lab AI-free hai.

COST:
- YE LAB LOCALLY 100% FREE hai. Sirf FastAPI + uvicorn chahiye, koi API key
  nahi, koi LLM call nahi, koi cloud spend nahi. TestClient bilkul offline.
- DEPLOY BUNDLE (deploy/ folder) ko Vercel par `vercel .` se deploy karna bhi
  Vercel ke HOBBY (free) plan par $0 hota hai for this tiny app — serverless
  function ka free tier itni chhoti app ke liye kaafi se zyada hai. Custom
  domain (optional) par hi registrar fee lagti hai. (L07: poora course ~$5-$10,
  mostly AWS-side; Vercel ka yeh hello-world hissa effectively free.)

DEPLOY ARTIFACTS (is folder me ready-to-ship):
- ./deploy/vercel.json            -> builds (@vercel/python) + routes (catch-all)
- ./deploy/requirements-vercel.txt -> fastapi + uvicorn (pinned-ish)
- Poore `vercel` CLI steps (npm i -g vercel -> vercel login -> vercel .) RUNBOOK
  me hain (Ed ke L01/L02 ke hisaab se). Yeh file sirf app + self-demo deta hai;
  actual cloud deploy ke commands runbook follow karo.
"""

import sys

from fastapi import FastAPI

# ---------------------------------------------------------------------------
# FASTAPI APP OBJECT
# ---------------------------------------------------------------------------
# FastAPI kya hai? Ek modern, async Python web framework. Yeh ek "app server"
# hai jo web requests ka jawab Python code chala kar deta hai. ASGI-based hai
# (async built-in), type hints use karta hai, aur /docs par auto Swagger UI
# deta hai. Flask ka faster, modern cousin samjho.
#
# IMPORTANT (Vercel ke liye): yeh `app` variable MODULE-LEVEL hona ZAROORI hai.
# Vercel ka @vercel/python runtime is module ko import karta hai aur `app` ko
# ASGI application ke roop me dhoondta hai. Agar `app` function ke andar chhupa
# ho to Vercel use nahi dhoondh payega. Isiliye hum ise top-level rakhte hain.
#
# title/version sirf /docs aur /openapi.json me dikhne ke liye — functional
# zaroorat nahi, par production me clean metadata achhi habit hai.
app = FastAPI(
    title="instant-prod",
    version="1.0.0",
    description="Ed Donner Production Track — Week1 Day1 instant deploy base.",
)

# App ka naam ek jagah rakha taaki /info aur logs me consistent rahe.
APP_NAME = "instant-prod"


# ---------------------------------------------------------------------------
# ROUTE 1: GET /  ->  "live from production"
# ---------------------------------------------------------------------------
# Ed ka classic Day-1 moment: deploy karne ke baad browser me "Live from
# production!" dikhta hai. Hum JSON return kar rahe hain (string ke bajaaye)
# kyunki production APIs typically JSON bolte hain — clients (frontend, curl,
# monitoring) ke liye structured response parse karna aasaan hota hai.
#
# @app.get("/") decorator FastAPI ko bolta hai: jab koi GET request ROOT path
# par aaye, yeh function chalao. Function se return hua dict ko FastAPI khud
# JSON response (Content-Type: application/json) me convert kar deta hai.
@app.get("/")
def read_root():
    """Root route — deployment alive hai ya nahi, yahi pehli proof hai."""
    return {"message": "live from production"}


# ---------------------------------------------------------------------------
# ROUTE 2: GET /health  ->  {"status": "ok"}
# ---------------------------------------------------------------------------
# Health-check endpoint production ki ROTI-MAKKHAN hai. Load balancers,
# container orchestrators (App Runner / ECS / k8s), aur uptime monitors is
# tarah ke endpoint ko baar-baar hit karte hain yeh confirm karne ke liye ki
# instance "healthy" hai. Agar health fail kare to traffic us instance par
# bhejna band kar diya jaata hai. Isiliye yeh hamesha LIGHT hona chahiye —
# koi DB query, koi LLM call nahi; bas "main zinda hoon" wala turant jawab.
@app.get("/health")
def health():
    """Liveness/health probe — load balancers/monitors isi ko poll karte hain."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# ROUTE 3: GET /info  ->  app name + Vercel-base note
# ---------------------------------------------------------------------------
# Ek chhota metadata/introspection endpoint. Production me aksar aisa route
# hota hai jo app ka naam, version, build/commit info deta hai — debugging aur
# "kaunsa version live hai?" verify karne ke liye. Yahan hum yeh bhi note kar
# rahe hain ki yahi app Vercel-deployable base hai (deploy/ bundle ke saath).
@app.get("/info")
def info():
    """App ka naam + note ki yeh Vercel-deployable base hai."""
    return {
        "app": APP_NAME,
        "version": "1.0.0",
        "note": (
            "This is the Vercel-deployable base app. Deploy bundle "
            "(vercel.json + requirements-vercel.txt) deploy/ folder me hai; "
            "`vercel .` ke poore steps runbook me hain."
        ),
        "llm": False,  # is lab me koi LLM nahi — pure deployment foundation
    }


# ===========================================================================
# CONCEPT NOTE — vercel.json ka builds + routes request ko app tak kaise
# pahunchata hai (Ed L01 me intuition develop karne ko bolta hai):
#
#   {
#     "builds": [ { "src": "instant.py", "use": "@vercel/python" } ],
#     "routes": [ { "src": "/(.*)",      "dest": "instant.py"     } ]
#   }
#
#   - builds: "is Python file ko @vercel/python runtime se ek serverless
#     function me build karo." Yaani Vercel hamare module ko import karke ek
#     lambda-jaisa function bana deta hai.
#   - routes: "/(.*)" ek catch-all regex hai — KOI BHI incoming path us
#     function (hamari app) ko de do. Phir FASTAPI internally apni routing
#     karta hai (/ , /health , /info ko sahi handler tak bhejta hai).
#
#   Flow:  browser GET /health
#            -> Vercel edge route "/(.*)" match
#            -> @vercel/python function (hamara module) invoke
#            -> FastAPI app /health handler chalata hai
#            -> {"status":"ok"} JSON wapas.
#
# Yeh deploy/vercel.json hamare module ke filename ke hisaab se likha hai —
# detail ke liye us file ke comments + runbook dekho.
# ===========================================================================


# ===========================================================================
# SELF-DEMO  — `uv run <file>` (NO args) yahi chalata hai.
# TestClient app ko IN-PROCESS hit karta hai (koi real network/port nahi),
# isiliye yeh offline, free, aur fast hai — aur HANG nahi karta.
# ===========================================================================
def run_self_demo():
    """TestClient se /, /health, /info hit karke results PRINT karo, exit 0."""
    # Import yahin (function ke andar) — taaki Vercel par module import karte
    # waqt test-only dependency load na ho aur cold start halka rahe.
    from fastapi.testclient import TestClient

    client = TestClient(app)

    print("\n" + "#" * 70)
    print("#  LAB 1 — Instant production deploy  (SELF-DEMO via TestClient)")
    print("#  No server, no browser, no API key. Pure offline check.")
    print("#" * 70 + "\n")

    # Har route ko hit karo aur status + JSON body dono dikhao. Yeh wahi cheez
    # hai jo deploy ke baad browser/curl me dikhti — bas yahan in-process.
    for path in ("/", "/health", "/info"):
        resp = client.get(path)
        print(f"GET {path:<8} -> HTTP {resp.status_code}")
        print(f"            body: {resp.json()}")
        print()

    print(">>> Local self-demo paas. Yahi app Vercel par deploy hone par")
    print(">>> '/' route browser me 'live from production' JSON dikhayega.")
    print(">>> Public karne ke liye: Vercel Deployment Protection (Vercel")
    print(">>> Authentication) toggle OFF karo — warna pehla deploy PRIVATE")
    print(">>> rehta hai (sirf logged-in team dekh sakti hai). [L02]")
    print("\n" + "#" * 70)
    print("#  LAB 1 complete (exit 0).")
    print("#" * 70 + "\n")


# ===========================================================================
# --serve  — asli uvicorn server (real browser/curl testing ke liye).
# Default (no args) -> self-demo. `--serve` -> live server on 127.0.0.1:8000.
# ===========================================================================
def run_server():
    """uvicorn se app ko 127.0.0.1:8000 par serve karo (Ctrl+C se stop)."""
    # uvicorn yahan import kiya (top par nahi) taaki self-demo path ko iski
    # zaroorat na pade — keep imports lazy, cold start light.
    import uvicorn

    print("\n[SERVE] uvicorn start: http://127.0.0.1:8000")
    print("[SERVE] Try: /  /health  /info  /docs   (Ctrl+C to stop)\n")
    # Locally hum uvicorn khud chalate hain; Vercel par yeh platform handle
    # karta hai (FastAPI = framework, uvicorn = ASGI server). Yahi L01 ka
    # "framework != server" wala point hai.
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    # sys.argv parse — agar "--serve" diya to live server, warna self-demo.
    # Default ko self-demo rakhna ZAROORI hai taaki `uv run <file>` kabhi hang
    # na kare (server foreground me block kar deta, automated runs atak jaate).
    if "--serve" in sys.argv:
        run_server()
    else:
        run_self_demo()
