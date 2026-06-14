"""
LAB 5 — CI/CD with GitHub Actions (automated deploy pipeline, LOCAL dry-run)
============================================================================
Title: Ek `git push` se "tested + packaged + deployed" tak ka poora pipeline —
       yahan LOCALLY simulate karke, step-by-step samajhte hue.

KYA SEEKHENGE (what concepts):
- CI/CD VALUE: har push -> automatically TEST -> BUILD -> DEPLOY. Manual clicking
  khatam; har change ek consistent, repeatable pipeline se guzarta hai. (L56/L62)
- GitHub Actions ANATOMY: triggers (`on: push` / `workflow_dispatch`), jobs
  (alag-alag ephemeral runner VMs), steps (sequential actions), aur secrets
  (`${{ secrets.* }}`). Sath wali `cicd/deploy.yml` exactly yahi dikhati hai. (L60)
- SECRETS MANAGEMENT: OIDC (recommended — short-lived token, no stored key) vs
  long-lived access keys (avoid — leak/rotate headache). (L59)
- TEST -> BUILD -> DEPLOY GATES: agar test fail, build nahi; build fail, deploy
  nahi. `needs:` se jobs chain hote hain — broken code prod me nahi jaata. (L60)
- LAMBDA contract: ek REAL `handler(event, context)` jo API-Gateway-proxy event
  padhta hai aur {statusCode, headers, body} return karta hai — yahi deploy hota.

KAISE CHALANA (how to run) — CWD = repo root:
    # 1) Default: poora pipeline DRY-RUN (test->package->deploy simulate), exit 0
    uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab5_cicd_pipeline.py

    # 2) Sirf Lambda zip build karo (yeh CI ka 'package' job karta hai)
    uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab5_cicd_pipeline.py --build-only

    # 3) Sirf handler() ko mock API-Gateway events ke saath invoke karke dekho
    uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab5_cicd_pipeline.py --invoke

DRY-RUN ka matlab: hum asli `aws`/`terraform` commands ko PRINT karte hain (taaki
real pipeline kya chalata samajh aaye) par EXECUTE nahi karte. Build (zip) aur
test (py_compile) REAL hote hain — woh local + free + safe hain.

LECTURE MAPPING: Ed Donner "AI Engineer Production Track", Week 2 · Day 5.
  L56 = GitHub Actions intro (actions/workflows/jobs)   L57 = git + setup
  L58 = repo + Terraform remote backend (S3 state)      L59 = OIDC IAM role
  L60 = deploy.yaml/destroy.yaml + 3 secrets             L61 = live pipeline deploy
  L62 = automated CI/CD git deploy (the loop)

COST: Is lab ko LOCALLY chalana = $0 (sirf zip banti hai + py_compile chalta hai;
  no AWS, no LLM). Public GitHub repo par Actions minutes bhi FREE. Asli AWS
  deploy (terraform apply jo yeh pipeline trigger karta) me Lambda/S3/API-GW/
  CloudFront/Bedrock — Ed ka course estimate ~$5-$10 (mostly free-tier). Pipeline
  khud koi extra charge nahi; jo deploy hota hai usi ka bill banta hai.
"""

import os
import sys
import json
import shutil
import zipfile
import py_compile
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# .env load. override=True => shell ki purani value ko .env override kar de
# (Ed Donner convention). Yahan key zaroori nahi — handler bina LLM ke bhi chalta.
load_dotenv(override=True)


# ---------------------------------------------------------------------------
# get_client: provider ke hisaab se (client, model) return. Default groq => free,
# OpenAI-compatible. Yeh lab LLM ko sirf OPTIONAL enrichment ke liye use karta
# hai (handler ek chhota AI-flavored response de) — key na ho to gracefully skip.
# NOTE the `or "placeholder"`: OpenAI() None api_key par CONSTRUCTION time hi
# crash karta hai, isliye placeholder daalna zaroori hai.
# ---------------------------------------------------------------------------
def get_client(provider: str = "groq"):
    """(client, model). Default groq => free, OpenAI-compatible. NOTE the `or "placeholder"`:
    OpenAI() None api_key par CONSTRUCTION time hi crash karta hai, isliye placeholder."""
    if provider == "groq":
        return OpenAI(base_url="https://api.groq.com/openai/v1",
                      api_key=os.getenv("GROQ_API_KEY") or "placeholder"), "llama-3.3-70b-versatile"
    if provider == "gemini":
        return OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                      api_key=os.getenv("GOOGLE_API_KEY") or "placeholder"), "gemini-2.5-flash"
    raise ValueError(f"Unknown provider: {provider}")


PROVIDER = "groq"

# Paths — saare absolute-ish (is file ke relative). Build artifacts yahin jaate.
HERE = Path(__file__).resolve().parent          # .../Practical
BUILD_DIR = HERE / "build"                       # zip yahan banti hai
ZIP_PATH = BUILD_DIR / "lambda.zip"              # CI isi path ko upload karta hai


# ===========================================================================
# ###############   THE DEPLOYABLE LAMBDA HANDLER (REAL)   ###################
# ===========================================================================
# Yahi function asli me AWS Lambda par chalta hai. API Gateway "proxy
# integration" mode me Lambda ko ek event dict deta hai jisme HTTP request
# ki saari details hoti hain (httpMethod, path, headers, body, ...). Handler ko
# ek dict return karna hota hai jisme statusCode/headers/body ho — API Gateway
# use HTTP response me convert karke client ko bhej deta hai.
#
# IMPORTANT: yahi handler CI/CD pipeline zip karke deploy karta hai. Local
# self-demo bhi ISI ko mock events ke saath call karta hai => "jo test kiya wahi
# deploy hua" (yahi CI/CD ka bharosa hai).
# ===========================================================================
def handler(event, context):
    """AWS Lambda + API-Gateway-proxy handler. Bina AWS/LLM ke bhi safely chalta hai."""
    # API Gateway proxy event se HTTP method, path, aur body nikaalo.
    # .get() defensive — kabhi-kabhi keys missing/None aati hain (direct invoke).
    method = (event or {}).get("httpMethod", "GET")
    path = (event or {}).get("path", "/")

    # body ek JSON STRING hoti hai (ya None). Safely parse karo.
    raw_body = (event or {}).get("body")
    try:
        body = json.loads(raw_body) if raw_body else {}
    except (json.JSONDecodeError, TypeError):
        body = {}

    # CORS headers — browser frontend (CloudFront) se call karne ke liye zaroori
    # (L45 me CORS dekha tha). Production me origin ko specific rakho, abhi '*'.
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
    }

    # --- Routing: ek chhota router (jaise FastAPI ke routes) ----------------
    # GET /health -> liveness probe (no LLM, no key). Load balancer isi ko poll karta.
    if path.endswith("/health") and method == "GET":
        return _resp(200, headers, {
            "status": "ok",
            "provider": PROVIDER,
            "llm_configured": bool(os.getenv("GROQ_API_KEY")),
        })

    # POST /chat -> asli kaam: prompt lo, LLM se reply (ya graceful fallback).
    if path.endswith("/chat") and method == "POST":
        prompt = body.get("prompt") or "Say hello in one short sentence."
        reply = _llm_reply(prompt)          # key na ho to fallback string deta hai
        return _resp(200, headers, {"prompt": prompt, "reply": reply})

    # Koi aur route -> 404 (clean JSON, crash nahi).
    return _resp(404, headers, {"error": "not found", "path": path, "method": method})


def _resp(status_code: int, headers: dict, payload: dict) -> dict:
    """API-Gateway-proxy response shape banata hai. body HAMESHA JSON string hota."""
    # statusCode int, headers dict, body STRING (json.dumps) — yahi contract hai.
    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(payload, ensure_ascii=False),
    }


def _llm_reply(prompt: str) -> str:
    """LLM se chhota reply; key/network na ho to graceful fallback (kabhi crash nahi).
    Production me yahi jagah Bedrock (Nova) call hoti — yahan groq free-tier se
    portable rakha hai (L47 OpenAI->Bedrock migration ka spirit)."""
    if not os.getenv("GROQ_API_KEY"):
        # GRACEFUL DEGRADATION (mandatory): key missing => live call skip, ek clear
        # fallback string do. Handler ka contract phir bhi poora hota hai, exit 0.
        return f"[no LLM key -> echo] {prompt}"
    try:
        client, model = get_client(PROVIDER)
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=64,              # cost cap (L07): output bounded
        )
        return r.choices[0].message.content
    except Exception as e:              # noqa: BLE001 — network/auth fail = degrade, crash nahi
        return f"[LLM call failed -> fallback] {type(e).__name__}: {e}"


# ===========================================================================
# ##################   BUILD: Lambda deployment ZIP (REAL)   ################
# ===========================================================================
# Yeh CI ka 'package' job hai. Hum is file ko ek zip me daalte hain — yahi
# artifact AWS Lambda par upload hota hai. Production me deps bhi bundle hoti
# (vendored / layer), par humara handler self-contained hai (sirf stdlib + env),
# isliye sirf is module ko zip kar rahe hain (clear + fast).
# ===========================================================================
def build_lambda_zip() -> Path:
    """Is file ko lambda.zip me pack karta hai (handler entrypoint). Path return."""
    # Fresh build dir — purana artifact hata ke clean zip banao (reproducible).
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    # Lambda runtime "lambda_function.handler" jaisa entrypoint expect karta hai
    # (module.function). Hum is file ko zip ke andar `lambda_function.py` naam se
    # rakhte hain taaki AWS handler config "lambda_function.handler" kaam kare.
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(__file__, arcname="lambda_function.py")

    return ZIP_PATH


# ===========================================================================
# ##############   LOCAL "TEST" GATE: py_compile (REAL)   ###################
# ===========================================================================
# CI ke 'test' job ka chhota local version. py_compile syntax/import-time errors
# pakadta hai — fast, free, no network. Real CI me yahan pytest bhi chalega.
# ===========================================================================
def run_local_test() -> bool:
    """Is file ko py_compile se verify karo. True = pass, False = fail."""
    try:
        # doraise=True => error par exception, taaki hum pakad sakein.
        py_compile.compile(__file__, doraise=True)
        return True
    except py_compile.PyCompileError as e:
        print(f"   [FAIL] py_compile error: {e}")
        return False


# ===========================================================================
# #################   DRY-RUN PIPELINE ORCHESTRATOR   #######################
# ===========================================================================
# Yeh `cicd/deploy.yml` ke 3 jobs ko LOCALLY mimic karta hai — test, package,
# deploy — har stage me samjhaata hai ki real GitHub Actions kya karta. Deploy
# stage me asli aws/terraform commands sirf PRINT hote hain (execute nahi).
# ===========================================================================
def _banner(title: str):
    """Ek saaf section banner — pipeline ke har stage ko visually alag karta."""
    print("\n" + "=" * 74)
    print(f"  {title}")
    print("=" * 74)


def stage_test() -> bool:
    """STAGE 1 — TEST (CI). Real py_compile + (real pipeline me) pytest."""
    _banner("STAGE 1/3 — TEST  (job: test)  ||  GitHub: runs-on ubuntu-latest")
    print("  CI me yeh steps chalte (cicd/deploy.yml dekho):")
    print("    - actions/checkout@v4         # repo code runner par laana")
    print("    - actions/setup-python@v5     # Python 3.12")
    print("    - astral-sh/setup-uv@v5       # uv install")
    print("    - run: uv sync                # deps (lockfile = reproducible)")
    print("    - run: uv run python -m py_compile ...   # compile gate")
    print("    - run: uv run pytest -q                  # unit test gate")
    print("\n  [LOCAL] Ab REAL py_compile chalata hoon handler par...")
    ok = run_local_test()
    print(f"  [LOCAL] py_compile result = {'PASS' if ok else 'FAIL'}")
    # GATE: test fail => poora pipeline yahin ruk jaata (broken code aage nahi).
    if not ok:
        print("  [GATE] test FAIL => package/deploy SKIP (broken code prod me nahi jaata).")
    return ok


def stage_package() -> bool:
    """STAGE 2 — PACKAGE (build). REAL lambda.zip banata hai."""
    _banner("STAGE 2/3 — PACKAGE  (job: package, needs: test)")
    print("  CI me yeh hota: zip build -> actions/upload-artifact@v4 (jobs ke")
    print("  beech share, kyunki har job alag VM par — disk share nahi hoti).")
    print("\n  [LOCAL] Ab REAL Lambda zip banata hoon...")
    zip_path = build_lambda_zip()
    size_kb = zip_path.stat().st_size / 1024
    print(f"  [LOCAL] Built: {zip_path}  ({size_kb:.1f} KB)")
    # Zip ke andar kya hai dikha do (entrypoint verify).
    with zipfile.ZipFile(zip_path) as zf:
        print(f"  [LOCAL] Zip contents: {zf.namelist()}  -> handler = lambda_function.handler")
    return True


def stage_deploy():
    """STAGE 3 — DEPLOY (CD). aws/terraform commands sirf PRINT (dry-run)."""
    _banner("STAGE 3/3 — DEPLOY  (job: deploy, needs: package)")

    # --- Secrets / OIDC samjhao -------------------------------------------
    print("  AUTH (L59): GitHub OIDC se short-lived creds — NO long-lived key.")
    print("  Required GitHub Secrets (Settings > Secrets and variables > Actions):")
    print("    - AWS_ROLE_ARN          # OIDC role ARN (Terraform se bana)")
    print("    - AWS_DEFAULT_REGION    # e.g. us-east-1")
    print("    - AWS_ACCOUNT_ID        # 12-digit account id")
    print("  OIDC vs keys: OIDC = auto-expiring + repo-scoped trust (RECOMMENDED).")
    print("                static keys = non-expiring, leak/rotate risk (AVOID).")

    # Local context me kya available hai woh transparently dikhao.
    has_creds = bool(os.getenv("AWS_ROLE_ARN") or os.getenv("AWS_ACCESS_KEY_ID"))
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    env = os.getenv("DEPLOY_ENV", "dev")

    print("\n  [DRY-RUN] Real pipeline yeh commands chalata (yahan sirf PRINT):")

    # 0) AWS creds configure (OIDC) — workflow me ek action karta, CLI equiv niche.
    print("\n   # 1) AWS credentials (OIDC) — workflow: aws-actions/configure-aws-credentials@v4")
    print(f"   #    role-to-assume: $AWS_ROLE_ARN   aws-region: {region}")

    # 1) terraform init — remote S3 backend (L58/L60).
    print("\n   # 2) terraform init (remote S3 backend — ephemeral runner par MUST)")
    print('   terraform init \\')
    print('     -backend-config="bucket=twin-terraform-state" \\')
    print('     -backend-config="key=twin/terraform.tfstate" \\')
    print(f'     -backend-config="region={region}" \\')
    print('     -backend-config="dynamodb_table=twin-terraform-locks" \\')
    print('     -backend-config="encrypt=true"')

    # 2) terraform workspace — dev/test/prod namespace (L54).
    print(f"\n   # 3) terraform workspace select {env}  (|| terraform workspace new {env})")
    print(f"   terraform workspace select {env} || terraform workspace new {env}")

    # 3) terraform apply -var-file (L49/L54 + task requirement).
    print(f"\n   # 4) terraform apply (-var-file) — infra create/update (IDEMPOTENT, L61)")
    print(f'   terraform apply -auto-approve -var-file="{env}.tfvars" -var="environment={env}"')

    # 4) lambda update-function-code — naya zip push.
    print("\n   # 5) update Lambda code (naya zip push)")
    print("   FN=$(terraform output -raw lambda_function_name)")
    print(f'   aws lambda update-function-code --function-name "$FN" \\')
    print(f"     --zip-file fileb://{ZIP_PATH} --publish")

    # 5) outputs / summary (L61 deployment summary). Output naam sibling
    #    terraform/outputs.tf se match (api_endpoint / memory_bucket_name).
    print("\n   # 6) outputs -> deployment summary (live URLs)")
    print("   terraform output -raw api_endpoint ; terraform output -raw memory_bucket_name")

    # --- Graceful "no AWS" message (mandatory) ----------------------------
    print()
    if not has_creds:
        print("  [INFO] AWS not configured (no AWS_ROLE_ARN / no access key) in this")
        print("         environment -> LOCAL FALLBACK: deploy commands SKIPPED, sirf")
        print("         dikhaye gaye. Zip REAL bani hai; bas AWS par push nahi hua.")
        print("         (boto3/aws CLI ki yahan zaroorat hi nahi — pure dry-run.)")
    else:
        print("  [INFO] AWS creds detected, par yeh DRY-RUN hai => phir bhi EXECUTE nahi")
        print("         kiya (safe demo). Real deploy GitHub Actions runner par hota hai.")


# ===========================================================================
# SELF-DEMO helpers — handler ko mock API-Gateway-proxy events ke saath invoke.
# ===========================================================================
def _mock_event(method: str, path: str, body: dict | None = None) -> dict:
    """Ek minimal API-Gateway-proxy event dict banata hai (jaisa AWS bhejta)."""
    return {
        "httpMethod": method,
        "path": path,
        "headers": {"Content-Type": "application/json"},
        # API Gateway body ko JSON STRING ke roop me deta hai (None bhi ho sakta).
        "body": json.dumps(body) if body is not None else None,
    }


def invoke_handler_demo():
    """Handler ko 3 mock events se call karke responses print karta hai."""
    _banner("HANDLER SELF-DEMO — mock API-Gateway-proxy events -> handler()")
    cases = [
        ("GET /health", _mock_event("GET", "/health")),
        ("POST /chat", _mock_event("POST", "/chat", {"prompt": "One-line: what is CI/CD?"})),
        ("GET /unknown", _mock_event("GET", "/unknown")),
    ]
    for label, event in cases:
        # context=None — local invoke me Lambda context object nahi hota (theek hai).
        resp = handler(event, None)
        print(f"\n  >>> {label}")
        print(f"      statusCode = {resp['statusCode']}")
        print(f"      body       = {resp['body']}")


# ===========================================================================
# RUN — full dry-run pipeline (default).
# ===========================================================================
def run_pipeline():
    """test -> package -> deploy ko LOCALLY orchestrate karta hai (dry-run)."""
    print("\n" + "#" * 74)
    print("#  LAB 5 — CI/CD PIPELINE (LOCAL DRY-RUN)  |  test -> package -> deploy")
    print("#  Mirror of cicd/deploy.yml (GitHub Actions). No AWS, no key needed.")
    print("#" * 74)

    # GATE chain: test pass -> package -> deploy. Yahi `needs:` ka local roop.
    if not stage_test():
        print("\n[PIPELINE] STOPPED at TEST gate. Fix code, phir push karo.")
        return 1                      # non-zero => "pipeline failed" (par self-demo me hum pass karenge)

    stage_package()
    stage_deploy()

    # Bonus: handler ko mock events se invoke karke dikhao ki "jo deploy hota wahi
    # local me test hua" — CI/CD ka bharosa visually.
    invoke_handler_demo()

    print("\n" + "#" * 74)
    print("#  PIPELINE COMPLETE (dry-run). Real repo me: yeh .github/workflows/deploy.yml")
    print("#  ban kar `git push` par GitHub runner par chalta -> dev auto-deploy (L61).")
    print("#  test/prod ko manual 'Run workflow' (workflow_dispatch) se promote karo.")
    print("#" * 74 + "\n")
    return 0


# ===========================================================================
# MAIN — flags: --build-only (sirf zip), --invoke (sirf handler), default = pipeline
# ===========================================================================
if __name__ == "__main__":
    if "--build-only" in sys.argv:
        # CI ka 'package' job isi mode ko call karta hai.
        p = build_lambda_zip()
        print(f"Built Lambda zip: {p}  ({p.stat().st_size / 1024:.1f} KB)")
        raise SystemExit(0)

    if "--invoke" in sys.argv:
        invoke_handler_demo()
        print()
        raise SystemExit(0)

    # Default: full dry-run pipeline. self-demo me hum HAMESHA exit 0 karte hain
    # (compile pass hota hai to run_pipeline 0 deta; agar kabhi test gate trip kare
    # to bhi self-demo crash na ho — par normal case me yeh 0 hi hoga).
    code = run_pipeline()
    raise SystemExit(code)
