"""
LAB 6 — Containerize for AWS (FastAPI app ready for ECR + App Runner)
====================================================================
Lecture mapping: Ed Donner "AI Engineer Production Track", Week 1 · Day 5
                 (L23 AWS setup + IAM, L24 cost monitoring/budgets,
                  L25 secure IAM users/groups, L26+L28 Docker images,
                  L29 ECR push, L30 App Runner auto-scaling + health check,
                  L31 Vercel -> AWS recap).

KYA SEEKHENGE (concepts is lab mein):
- WHY containerize: "parity" + "portability". Jo image tumhare laptop par
  chali, BILKUL wahi AWS App Runner par chalegi — "works on my machine"
  problem khatam. Yahi Vercel (auto-build) se AWS (apna Dockerfile) ki taraf
  shift ka asli karan hai: tum apne runtime ka control le lete ho.
- 12-FACTOR CONFIG: saari deploy-specific cheezein (version, port, API keys)
  ENVIRONMENT VARIABLES se aati hain, code mein hardcode NAHI. Ek hi image,
  alag-alag env vars => alag-alag environments (local / staging / prod).
- APP RUNNER HEALTH CHECK: /health ek alag, SUPER-LIGHT route hai jo App
  Runner har 20s mein hit karta hai (L30). Ismein DB/LLM call MAT karo —
  warna timeout (5s) par App Runner galti se "unhealthy" maan lega aur
  container ko maar dega. Health = "process zinda hai", kuch aur nahi.
- LLM call with GRACEFUL fallback: /generate ek chhota LLM call karta hai,
  par agar GROQ_API_KEY missing ho to crash/hang nahi karta — clean message
  return karta hai (production app kabhi ek missing-key par 500 nahi dena
  chahiye is demo route ke liye).

KAISE CHALANA (exact commands):
    # 1) Default (NO args) => built-in TestClient self-demo, prints + exit 0.
    #    API key ki zaroorat NAHI — /generate gracefully degrade karta hai.
    uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab6_containerize_for_aws.py

    # 2) --serve => real uvicorn server (browser/curl se test karne ke liye).
    uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab6_containerize_for_aws.py --serve
    #    Phir browser: http://127.0.0.1:8000/   |   curl http://127.0.0.1:8000/health

COST (yeh deployment course hai, isliye paisa-spasta saaf likh rahe hain):
- Is lab ko LOCALLY chalana = 100% FREE. Self-demo bina kisi API key ke
  chalta hai (Groq optional hai aur Groq ka free tier hai). Local Docker
  build/run bhi free (sirf tumhari machine ke resources).
- CLOUD deploy (jo RUNBOOK mein hai) ka realistic estimate (L24 ke mutabik):
  agar App Runner ¼ vCPU + 0.5 GB poora MAHINA chalta rahe to ~$1-$5/month.
  Agar tum 2 din mein TEARDOWN kar do to cost ~$0 (de minimis). AWS par koi
  HARD SPEND CAP nahi hota — sirf budget alerts (L24). Isliye runbook mein:
  zero-spend budget + monthly budget banao, aur kaam ke baad App Runner +
  ECR image delete karke (TEARDOWN) bill zero rakho.

NOTE — heavy AWS steps yahan NAHI hain (jaan-boojh kar):
  IAM user + group (L23/L25), ECR repo banana (L29), AWS CLI configure,
  docker login/build --platform linux/amd64/tag/push (L29), App Runner
  service + auto-scaling + health-check config (L30), COST MONITORING
  budgets (L24), aur TEARDOWN — yeh sab ek alag RUNBOOK (.md) mein hain.
  Yeh file sirf "container ke andar kya chalega" define karti hai — woh
  artifact jise Dockerfile package karega aur App Runner serve karega.
"""

import os
import sys

from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

# load_dotenv(override=True): agar shell aur .env dono mein same var ho to
# .env wali jeet jaaye (Ed isi convention par chalta hai). LOCAL dev ke liye
# .env handy hai. PRODUCTION (App Runner) mein .env file nahi jaati —
# wahaan App Runner UI se env vars inject hote hain (12-factor). Code dono
# jagah same — bas source alag. override=True sirf local convenience hai.
load_dotenv(override=True)


# ---------------------------------------------------------------------------
# get_client: provider ke hisaab se (client, model) deta hai.
# Groq aur Gemini dono OpenAI-compatible hain — bas base_url alag.
# Default = groq => zero cost, fast. (Course-wide standard helper, inline.)
# ---------------------------------------------------------------------------
def get_client(provider: str = "groq"):
    """(client, model) return karta hai. Default groq => zero cost, fast, OpenAI-compatible."""
    if provider == "groq":
        return OpenAI(base_url="https://api.groq.com/openai/v1",
                      api_key=os.getenv("GROQ_API_KEY") or "placeholder"), "llama-3.3-70b-versatile"
    if provider == "gemini":
        return OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                      api_key=os.getenv("GOOGLE_API_KEY") or "placeholder"), "gemini-2.5-flash"
    raise ValueError(f"Unknown provider: {provider}")


# ---------------------------------------------------------------------------
# FastAPI app object. NOTE: Dockerfile/uvicorn isi "app" ko dhoondhta hai —
# CMD ["uvicorn", "lab6_containerize_for_aws:app", ...]. Matlab module ka
# naam : variable ka naam. Isliye variable ka naam EXACTLY `app` rakhna
# zaroori hai (App Runner + Dockerfile dono isi naam par depend karte hain).
# ---------------------------------------------------------------------------
app = FastAPI(title="Production AI App on AWS", version=os.getenv("APP_VERSION", "1.0.0"))


# Pydantic request model /generate ke liye. FastAPI ise automatically
# validate karta hai (galat JSON => 422), aur /docs mein schema dikhata hai.
class GenerateRequest(BaseModel):
    prompt: str = "Say hello from inside a Docker container on AWS."


# ===========================================================================
# ROUTE: GET /  — root, ek simple "app zinda hai" landing JSON.
# Browser ya curl se sabse pehle yahi hit karte ho deploy verify karne ke liye.
# ===========================================================================
@app.get("/")
def root():
    return {"message": "production AI app on AWS"}


# ===========================================================================
# ROUTE: GET /health  — APP RUNNER KA HEALTH-CHECK TARGET (L30).
# App Runner config mein humne Path=/health, Protocol=HTTP, timeout=5s,
# interval=20s set kiya tha. App Runner har 20s mein yeh hit karta hai;
# agar 5 baar lagatar fail/timeout ho to container ko UNHEALTHY maan ke
# replace kar deta hai.
#
# CRITICAL DESIGN RULE: yeh route ULTRA-LIGHT hona chahiye —
#   - koi DB query NAHI
#   - koi LLM/API call NAHI (warna 5s timeout par false-unhealthy)
# Bas process zinda hai => instant {"status":"healthy"}. Yahi Kubernetes
# liveness probe + ALB target-group health check ka combo pattern hai.
# Dockerfile ka HEALTHCHECK bhi isi route ko hit karta hai (do jagah, ek hi
# truth: "process up?").
# ===========================================================================
@app.get("/health")
def health():
    return {"status": "healthy"}


# ===========================================================================
# ROUTE: GET /version  — 12-FACTOR CONFIG ka live demo.
# APP_VERSION ek ENV VAR se aati hai (default "1.0.0" agar set nahi hai).
# WHY: ek hi immutable image ko alag environments mein deploy karte ho;
# version/build-info code mein hardcode karne ki bajaye env se inject karte
# ho. App Runner UI mein "Add environment variable" => APP_VERSION=1.2.3
# karke tum nayi image build kiye bina bhi reported version badal sakte ho
# (ya CI build-time par inject kar sakte ho). Operator ko deploy verify
# karne ke liye yeh handy hota hai.
# ===========================================================================
@app.get("/version")
def version():
    return {"version": os.getenv("APP_VERSION", "1.0.0")}


# ===========================================================================
# ROUTE: POST /generate  — chhota LLM call, GRACEFUL no-key fallback ke saath.
# Production app mein yahi tumhara asli "AI" endpoint hota (yahan minimal).
#
# GRACEFUL DEGRADE: agar GROQ_API_KEY missing/empty hai to hum LLM call
# karte hi NAHI — turant ek clean JSON return karte hain. WHY: deploy ke
# time agar operator env var set karna bhool jaaye, app crash/hang nahi
# honi chahiye — ek saaf "key missing" signal dena chahiye (502/hang se
# behtar). Self-demo (bina key) ke liye bhi yahi raasta exit 0 deta hai.
# ===========================================================================
@app.post("/generate")
def generate(req: GenerateRequest):
    api_key = os.getenv("GROQ_API_KEY")

    # No-key fallback: LLM ko chhua tak nahi — clean, fast, predictable.
    if not api_key:
        return {
            "ok": False,
            "reason": "GROQ_API_KEY missing — skipping live LLM call (graceful fallback).",
            "echo_prompt": req.prompt,
        }

    # Key hai to actual LLM call. try/except taaki network/quota/bad-key
    # par bhi route 500 thik se return kare, process zinda rahe.
    try:
        client, model = get_client("groq")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": req.prompt}],
            temperature=0.7,
            max_tokens=120,  # chhota rakha — demo ke liye sasta + fast
        )
        return {
            "ok": True,
            "model": model,
            "output": response.choices[0].message.content.strip(),
        }
    except Exception as e:
        # Yahan bhi crash nahi — caller ko structured error do.
        return {"ok": False, "reason": f"LLM call failed: {e}", "echo_prompt": req.prompt}


# ===========================================================================
# SELF-DEMO — default `uv run <file>` (NO args) ise chalata hai.
# Built-in TestClient se apne hi routes ko in-process hit karta hai (koi
# server boot nahi, koi network nahi) — fast + deterministic. Sab print
# karke EXIT 0. Yeh CI/local sanity check hai: "container ke andar jo chalega
# woh ka actually responds correctly?"
# ===========================================================================
def run_self_demo():
    from fastapi.testclient import TestClient  # local import — sirf demo ke liye

    print("\n" + "#" * 72)
    print("#  LAB 6 — Containerize for AWS  (built-in TestClient self-demo)")
    print("#  (no server boot, no network — apne hi routes ko in-process call)")
    print("#" * 72 + "\n")

    client = TestClient(app)

    # --- GET / -----------------------------------------------------------
    r = client.get("/")
    print(f"GET /         -> {r.status_code}  {r.json()}")

    # --- GET /health  (App Runner health-check target) -------------------
    r = client.get("/health")
    print(f"GET /health   -> {r.status_code}  {r.json()}   (App Runner har 20s isko hit karega)")

    # --- GET /version  (APP_VERSION env var) -----------------------------
    r = client.get("/version")
    print(f"GET /version  -> {r.status_code}  {r.json()}   (APP_VERSION env se; default 1.0.0)")

    # --- POST /generate  (LLM call ya graceful no-key fallback) ----------
    r = client.post("/generate", json={"prompt": "Ping from the self-demo."})
    body = r.json()
    print(f"POST /generate-> {r.status_code}  ok={body.get('ok')}")
    if body.get("ok"):
        print(f"    LLM output: {body.get('output')}")
    else:
        # Hinglish "key missing, skipping live call" message (graceful path).
        print(f"    key missing / call skipped, live call skip kar diya: {body.get('reason')}")

    print("\n" + "#" * 72)
    print("#  LAB 6 self-demo complete. Routes OK. Ab is file ko Dockerize karke")
    print("#  ECR -> App Runner par deploy karna (steps RUNBOOK .md mein).")
    print("#  Local run = FREE. Cloud deploy ~$1-$5/month (teardown se ~$0).")
    print("#" * 72 + "\n")


# ===========================================================================
# MAIN — `--serve` => real uvicorn; warna self-demo.
# sys.argv parse: simplest possible flag handling (no argparse zaroorat).
# ===========================================================================
if __name__ == "__main__":
    if "--serve" in sys.argv:
        # Real server — browser/curl se test karne ke liye. host 127.0.0.1
        # (sirf local). NOTE: container ke andar uvicorn host 0.0.0.0 par
        # chalta hai (sab interfaces) — woh Dockerfile ke CMD mein hai, taaki
        # App Runner bahar se reach kar sake. Yahan local-only 127.0.0.1.
        import uvicorn
        print("[serve] uvicorn on http://127.0.0.1:8000  (Ctrl+C to stop)")
        print("[serve] try: curl http://127.0.0.1:8000/health")
        uvicorn.run(app, host="127.0.0.1", port=8000)
    else:
        # Default: self-demo, exit 0 (chahe API key ho ya na ho).
        run_self_demo()
