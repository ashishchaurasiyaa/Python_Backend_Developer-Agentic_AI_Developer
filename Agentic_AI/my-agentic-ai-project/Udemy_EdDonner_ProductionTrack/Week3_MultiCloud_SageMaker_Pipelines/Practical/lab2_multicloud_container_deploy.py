"""
LAB 2 — Multi-cloud container deploy: Azure Container Apps & GCP Cloud Run
=========================================================================
Title: EK chhota FastAPI agent (GET /health, POST /chat) likho jo ek Docker container
       ka WORKLOAD hai, aur dikhao ki BILKUL WAHI container Azure Container Apps PAR bhi
       chalta hai aur GCP Cloud Run par bhi — bina ek line code change. "Build once,
       run anywhere" — yahi is lab ka asli sabak (parity = lesson).

KYA SEEKHENGE (what concepts):
- BUILD-ONCE-RUN-ANYWHERE: ek hi Dockerfile + ek hi FastAPI app = ek immutable artifact
  (image). Wahi artifact local par, Azure par, GCP par chalta hai. Tumhari app ko pata
  hi nahi ki neeche kaunsa cloud hai — image SAME hai (L66: "box within a box"; L73:
  "same code, 4 environments"). Yeh dev/prod PARITY hai jo "works on my machine" bug
  khatam karti hai.
- AZURE CONTAINER APPS vs GCP CLOUD RUN: dono "managed serverless containers" hain
  (container-as-a-service tier, L73 ka deployment spectrum ka sweet-spot). Tum ek image
  doge, platform usse on-demand chalata hai, traffic par auto-scale, idle par scale-to-
  zero. AWS App Runner inka teesra bhai hai. Inka CONTRACT same hai: "ek container, ek
  port (8000), ek health endpoint" — isliye SAME image dono par fit ho jaata hai.
- TERRAFORM DONO PROVIDERS KO EK JAISA ABSTRACT KARTA HAI: Azure ke liye `azurerm`,
  GCP ke liye `google` — provider block alag, par WORKFLOW identical
  (init -> plan -> apply -> destroy). Yeh deploy/ folder ke 2 .tf files me dikhta hai:
  azure_container_app.tf aur gcp_cloud_run.tf — dono ek hi image (var.image) ko point
  karte hain, dono port 8000 expose karte hain. IaC ki asli power = PORTABILITY (L68/L72).
- FASTAPI WORKLOAD: GET /health (cloud ki HEALTHCHECK / liveness probe ise hit karti hai —
  Dockerfile ka HEALTHCHECK, ACA/Cloud Run ka readiness) + POST /chat (asli agent call,
  get_client groq fallback ke peeche). Yeh wahi shape hai jo Ed ke cyber-analyzer app me
  tha (FastAPI + uvicorn 0.0.0.0:8000), bas hum ek MINIMAL self-contained version likh
  rahe hain (Semgrep/MCP ke bina) taaki lab ek-file me chale.
- GRACEFUL DEGRADE + OFFLINE: is env me na API key zaroori, na az/gcloud CLI, na koi
  cloud creds. /chat bina GROQ_API_KEY ke bhi 200 deta hai (saaf placeholder text) —
  NA crash, NA hang, NA network. Self-demo TestClient se in-process /health + /chat
  hit karta hai (koi real port/socket bhi nahi kholta).

KAISE CHALANA (how to run) — CWD = repo root (my-agentic-ai-project):
    # Default: self-demo (no key / no cloud / no CLI bhi chalega, exit 0)
    uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab2_multicloud_container_deploy.py

    # App ko REAL uvicorn server ki tarah chalana ho (container ke andar jaisa):
    uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab2_multicloud_container_deploy.py --serve
    #   -> uvicorn 0.0.0.0:8000; phir: curl localhost:8000/health
    #      curl -XPOST localhost:8000/chat -d '{"message":"hi"}' -H 'content-type: application/json'

    # Real container me yahi entrypoint chalta hai (deploy/Dockerfile CMD):
    #   uvicorn lab2_multicloud_container_deploy:app --host 0.0.0.0 --port 8000

LECTURE MAPPING: Ed Donner "AI Engineer Production Track", Week 3 · Day 1-2.
  L66 = Containerizing AI Agents with Docker (multi-stage build; FastAPI/uvicorn serve;
        HEALTHCHECK + EXPOSE 8000; "build once locally, deploy anywhere"; image vs container).
  L67 = Setting Up Azure Infrastructure (Account -> Subscription -> Resource Group ->
        Resources; budget alert; az CLI + az login; resource group cyber-analyzer-rg).
  L68 = Deploying to Azure with Terraform (azurerm provider; ACR; container app environment
        + container app; platform=linux/amd64; resource providers register; plan/apply).
  L69 = AI Agents + MCP on Azure Container Apps (LIVE app on azurecontainerapps.io;
        Log Stream; ingress on port 8000; terraform destroy).
  L70/L71/L72 = GCP infra + gcloud CLI + Cloud Run via Terraform (google provider;
        google_cloud_run_v2_service from an image; IAM invoker allUsers; scale-to-zero;
        memory gotcha; same plan/apply workflow).
  L73 = Deploying across GCP + Azure (4 parallel deployments of SAME container; deployment
        spectrum PaaS->CaaS->serverless->server->orchestration; ACA & Cloud Run = CaaS
        sweet-spot; always destroy).

COST: Is lab ko LOCALLY chalana = $0. Sirf in-process TestClient (koi socket/port/network
  nahi), aur GROQ_API_KEY na ho to /chat live call SKIP karke placeholder text deta hai —
  phir bhi EXIT 0, zero cost, zero crash.
  REAL CLOUD deploy (runbook, deploy/*.tf se):
    * Azure Container Apps: consumption plan — idle par scale-to-zero (=$0 jab traffic nahi).
      Active par vCPU-second + GiB-second billing; ek demo app pe daily kuch cents
      (L69 me Ed ko ~$0.17/day laga tha jab galti se chalu chhod diya). Free credits
      (~$200/30din) me aaram se aata hai. ACR Basic ~$0.167/day (~$5/mo).
    * GCP Cloud Run: bhi scale-to-zero, idle=$0; per-request + vCPU/memory-second billing,
      bada free tier (~2M req/mo). Demo me effectively free.
  Dono CaaS hain => `terraform destroy` ke baad recurring cost ~$0 (L69/L73: ALWAYS destroy).
"""

import json
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

# .env load. override=True => .env value shell ki purani value ko jeet jaaye (Ed ki
# convention). Container me yeh keys --env-file / ACA secret / Cloud Run env var se
# inject hoti hain (L66: secrets image me bake NAHI, runtime par inject) — local me .env.
load_dotenv(override=True)


# ===========================================================================
# get_client — LLM client. EXACT helper (placeholder fix ke saath).
# ===========================================================================
# Groq/Gemini OpenAI-compatible hain — sirf base_url alag. Default groq => free.
# /chat endpoint isi ke peeche call karta hai. Yeh helper kisi cloud-specific cheez par
# depend NAHI karta — yahi to point hai: app cloud-agnostic hai, image har jagah same.
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
# call_agent — POST /chat ka DIL. provider abstraction + graceful no-key.
# ===========================================================================
# Yeh wahi business logic hai jo container ke andar chalta hai. Isse koi farak nahi
# padta ki container Azure par hai ya GCP par ya local — SAME function. Cloud sirf
# "yeh container chalao + port 8000 par traffic bhejo" karta hai (CaaS contract).
def call_agent(message: str) -> dict:
    """User message -> {reply, model, llm_called}. Bina GROQ_API_KEY ke bhi kaam karta
    hai (graceful): live call SKIP karke ek saaf placeholder reply deta hai. NA crash."""
    key = os.getenv("GROQ_API_KEY")
    if not key:
        # No key => LIVE call mat karo (warna network/auth error). Graceful degrade:
        # placeholder reply, taaki /chat ka shape dikhe aur container "healthy" rahe.
        return {
            "reply": "[SKIPPED live LLM call: GROQ_API_KEY missing => local cost $0. "
                     "Key set karo (.env / ACA secret / Cloud Run env var) to yahan "
                     "real groq output aayega — SAME container, koi code change nahi.]",
            "model": "none",
            "llm_called": False,
        }

    # Key hai => asli call. groq free-tier, OpenAI-compatible chat.completions.
    client, model = get_client("groq")
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a concise multi-cloud demo agent. "
                                          "Reply in one short sentence."},
            {"role": "user", "content": message},
        ],
        max_tokens=128,   # output cap = cost brake (chhota rakho, demo hai)
    )
    return {
        "reply": resp.choices[0].message.content,
        "model": model,
        "llm_called": True,
    }


# ===========================================================================
# THE CONTAINERIZED WORKLOAD — FastAPI app (yahi cloud par chalta hai)
# ===========================================================================
# Ek MINIMAL FastAPI app, exactly wahi shape jo Ed ke cyber-analyzer me tha:
#   - FastAPI + uvicorn, 0.0.0.0:8000
#   - GET /health   -> cloud ki liveness/readiness probe + Dockerfile HEALTHCHECK ise hit
#                      karti hai. Healthy na ho to ACA/Cloud Run container ko restart/replace
#                      kar dega. Isliye yeh CHHOTA, FAST, dependency-free hona chahiye —
#                      yahan koi LLM call NAHI (warna no-key par bhi yeh sasta rehna chahiye).
#   - POST /chat    -> asli agent workload (call_agent ke peeche).
#
# DESIGN: fastapi/starlette ko top par import karte hain (env me available hai). Agar
# kabhi missing ho to `--serve`/`app` use karte waqt clear error aata — par self-demo
# bhi inhi par TestClient se chalta hai, isliye yeh lab ka core dependency hai (boto3
# jaisi OPTIONAL nahi). Phir bhi hum TestClient ko lazy import karte hain (neeche).
# ---------------------------------------------------------------------------
from fastapi import FastAPI, Request  # noqa: E402  (docstring + load_dotenv ke baad jaan-boojh ke)

# App object — yahi wo `app` hai jise uvicorn dhoondta hai:
#   uvicorn lab2_multicloud_container_deploy:app --host 0.0.0.0 --port 8000
# (deploy/Dockerfile ka CMD aur ACA/Cloud Run container dono isi ko chalate hain.)
app = FastAPI(
    title="multi-cloud container demo agent",
    description="SAME container Azure Container Apps + GCP Cloud Run dono par chalta hai.",
    version="1.0.0",
)


@app.get("/health")
def health():
    """Liveness/readiness probe. Cloud ka load balancer + Dockerfile HEALTHCHECK ise hit
    karta hai. JAAN-BOOJH ke koi LLM/network call NAHI — sasta + deterministic. Ek field
    `cloud` bhi return karta hai jo env var se aata hai: yahi prove karta hai ki SAME image
    Azure par CLOUD=azure, GCP par CLOUD=gcp set karke run hota hai (image badalti NAHI)."""
    return {
        "status": "ok",
        # CLOUD env var = sirf LABEL (Terraform har platform par alag set karta hai).
        # Image identical; runtime config alag. Yahi build-once-run-anywhere ka proof.
        "cloud": os.getenv("CLOUD", "local"),
        # Konsa provider live hoga jab key ho (config visibility, L69 health check jaisa).
        "llm_provider": "groq",
        "llm_key_present": bool(os.getenv("GROQ_API_KEY")),
    }


@app.post("/chat")
async def chat(request: Request):
    """POST /chat {"message": "..."} -> {"reply", "model", "llm_called", "cloud"}.
    Asli agent workload. Bina key ke bhi 200 (graceful). Garbage body par 400, crash nahi."""
    # Body parse — defensive. Container ko kabhi unhandled 500 nahi dena (L69 jaisa robust).
    try:
        data = await request.json()
    except Exception:
        # Invalid/empty JSON => 400 (production input validation), crash nahi.
        return _json(400, {"error": "invalid JSON body; expected {'message': '...'}"})

    message = (data or {}).get("message")
    if not message:
        return _json(400, {"error": "missing 'message' field"})

    # call_agent graceful hai — key na ho to placeholder, ho to real groq.
    result = call_agent(message)
    # `cloud` field response me bhi daal do — taaki client dekh sake ki kis cloud ke
    # container ne reply diya (Azure vs GCP), bina image badle. Parity ka live proof.
    result["cloud"] = os.getenv("CLOUD", "local")
    return _json(200, result)


def _json(status_code: int, payload: dict):
    """Chhota helper: explicit status_code ke saath JSONResponse. (FastAPI default 200
    deta hai; humein 400 bhi chahiye, isliye explicit.)"""
    from fastapi.responses import JSONResponse  # lazy: sirf yahan chahiye
    return JSONResponse(status_code=status_code, content=payload)


# ===========================================================================
# SELF-DEMO — `uv run <file>` (no args) yahan aata hai. TestClient se in-process.
# ===========================================================================
# TestClient (starlette/httpx ke upar) app ko IN-PROCESS chalata hai — koi real socket,
# port, ya network NAHI. Yeh bilkul wahi hai jaise cloud ki health-probe + ek user
# /chat hit karta — par offline, free, deterministic. Isse hum dikhate hain ki container
# ka WORKLOAD chal raha hai, chahe abhi koi cloud na ho.
def _print_parity_explainer():
    """Build-once-run-anywhere + ACA vs Cloud Run + Terraform parity — sirf print,
    koi call nahi. Yahi L66/L72/L73 ka teaching core hai."""
    print("=" * 74)
    print("BUILD ONCE, RUN ANYWHERE  (parity = is lab ka sabak)")
    print("=" * 74)
    print("Ek hi artifact (Docker image) -> 3+ jagah, ZERO code change:")
    print("  1) local       : uvicorn ...:app  (ya `--serve`)")
    print("  2) local Docker : docker run -p 8000:8000 <image>   (L66 'box in a box')")
    print("  3) Azure ACA    : deploy/azure_container_app.tf  -> ingress 8000")
    print("  4) GCP Cloud Run: deploy/gcp_cloud_run.tf         -> port 8000")
    print("Image IDENTICAL rehti hai; sirf runtime CONFIG (env var CLOUD=, API key) badalta.")
    print()
    print("AZURE CONTAINER APPS  vs  GCP CLOUD RUN  (dono = managed serverless containers)")
    print("-" * 74)
    print(f"{'aspect':<22}{'Azure Container Apps':<28}{'GCP Cloud Run'}")
    print(f"{'tier (L73)':<22}{'container-as-a-service':<28}{'container-as-a-service'}")
    print(f"{'you provide':<22}{'a Docker image':<28}{'a Docker image'}")
    print(f"{'scaling':<22}{'auto + scale-to-zero':<28}{'auto + scale-to-zero'}")
    print(f"{'port contract':<22}{'ingress targetPort 8000':<28}{'containerPort 8000'}")
    print(f"{'image registry':<22}{'ACR (azurerm)':<28}{'Artifact Registry/GCR'}")
    print(f"{'terraform provider':<22}{'azurerm':<28}{'google'}")
    print(f"{'public access':<22}{'ingress external=true':<28}{'IAM run.invoker allUsers'}")
    print(f"{'AWS sibling':<22}{'App Runner':<28}{'App Runner'}")
    print()
    print(">> SAME container fit ho jaata hai DONO par kyunki dono ka contract same hai:")
    print("   'ek image + ek port (8000) + ek /health endpoint'. (L66/L73)")
    print()
    print(">> TERRAFORM dono ko EK JAISA abstract karta hai: provider block alag (azurerm")
    print("   vs google) par WORKFLOW identical: init -> plan -> apply -> destroy. (L68/L72)")
    print()


def run_self_demo():
    """TestClient se /health + /chat hit karo (graceful no-key), print karo, exit 0.
    Koi cloud / CLI / key / socket nahi chahiye."""
    print("\n" + "#" * 74)
    print("#  LAB 2 SELF-DEMO — multi-cloud container deploy  (no cloud/CLI/key bhi OK)")
    print("#" * 74 + "\n")

    # --- 1) Parity teaching (build-once-run-anywhere; ACA vs Cloud Run; Terraform) ---
    _print_parity_explainer()

    # --- 2) TestClient: container ke WORKLOAD ko in-process chalao ----------
    # TestClient ko lazy import: starlette.testclient -> httpx. Dono env me hain. Lazy
    # rakhne se top-level import surface chhota rehta hai aur error (agar ho) yahin saaf
    # dikhta hai bajay module-load par.
    try:
        from fastapi.testclient import TestClient
    except Exception as e:  # pragma: no cover (env me available hai)
        print(f"[INFO] TestClient import nahi hua ({e}) => self-demo skip, par exit 0.")
        print("[INFO] App object (`app`) phir bhi valid hai; `--serve` se chala sakte ho.")
        raise SystemExit(0)

    # TestClient app ko IN-PROCESS wrap karta hai — koi real port/socket nahi khulta.
    client = TestClient(app)

    print("=" * 74)
    print("WORKLOAD TEST via TestClient  (cloud ki health-probe + ek user request jaisa)")
    print("=" * 74)

    # --- GET /health — yahi probe ACA/Cloud Run + Dockerfile HEALTHCHECK hit karti hai -
    print("GET /health   (liveness/readiness probe — cloud isi se decide karta 'healthy?')")
    r = client.get("/health")
    print(f"  statusCode = {r.status_code}")
    print("  body       = " + json.dumps(r.json(), ensure_ascii=False))
    print()

    # --- POST /chat (valid) — asli agent workload (graceful no-key) --------
    print("POST /chat   (asli agent workload; bina key ke bhi 200 — graceful)")
    body = {"message": "In one short line: why run the SAME container on Azure AND GCP?"}
    print(f"  request body = {json.dumps(body, ensure_ascii=False)}")
    r = client.post("/chat", json=body)
    print(f"  statusCode = {r.status_code}")
    print("  body       = " + json.dumps(r.json(), indent=2, ensure_ascii=False))
    print()

    # --- POST /chat (garbage) — 400, crash nahi (robustness proof) ---------
    print("POST /chat   (missing 'message' => clean 400, container crash NAHI hota)")
    r = client.post("/chat", json={"oops": 1})
    print(f"  statusCode = {r.status_code}")
    print("  body       = " + json.dumps(r.json(), ensure_ascii=False))
    print()

    # --- 3) Deploy artifacts pointer ---------------------------------------
    print("=" * 74)
    print("REAL DEPLOY ARTIFACTS  (deploy/ folder — same image, 2 clouds)")
    print("=" * 74)
    here = os.path.dirname(os.path.abspath(__file__))
    for fn, what in [
        ("deploy/Dockerfile", "image build: python:3.12-slim, uvicorn 0.0.0.0:8000, EXPOSE+HEALTHCHECK"),
        ("deploy/azure_container_app.tf", "azurerm: resource group + container app env + container app (ingress 8000)"),
        ("deploy/gcp_cloud_run.tf", "google: cloud_run_v2_service from image + IAM invoker (allUsers)"),
    ]:
        full = os.path.join(here, fn)
        exists = "OK" if os.path.exists(full) else "MISSING"
        print(f"  [{exists}] {fn}")
        print(f"         {what}")
    print()
    print("Workflow (L68/L72): build image -> push to registry -> `terraform apply` in")
    print("deploy/ (azure ya gcp) -> live URL. Cleanup: `terraform destroy` (L69/L73 ALWAYS).")
    print()

    print("#" * 74)
    print("#  LAB 2 complete. SAME FastAPI container = build-once-run-anywhere;")
    print("#  Azure Container Apps & GCP Cloud Run = managed serverless containers (CaaS);")
    print("#  Terraform dono providers ko ek-jaisa abstract karta hai (init/plan/apply).")
    print("#" * 74 + "\n")

    raise SystemExit(0)


# ===========================================================================
# MAIN — default self-demo; --serve => real uvicorn (container entrypoint jaisa).
# ===========================================================================
if __name__ == "__main__":
    if "--serve" in sys.argv:
        # REAL server mode — bilkul wahi jo container ke andar chalta hai. Yeh BLOCKING
        # hai (port 8000 par listen). Self-demo NAHI — yeh explicit `--serve` par hi.
        import uvicorn
        print("[serve] uvicorn 0.0.0.0:8000  ->  GET /health , POST /chat")
        print("[serve] (container ke andar yahi entrypoint chalta hai; Ctrl+C to stop)")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        run_self_demo()
