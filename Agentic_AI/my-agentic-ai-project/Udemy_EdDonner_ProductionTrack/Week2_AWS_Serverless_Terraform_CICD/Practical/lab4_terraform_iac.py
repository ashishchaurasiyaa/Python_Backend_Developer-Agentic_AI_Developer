"""
LAB 4 — Infrastructure as Code with Terraform (multi-environment serverless stack)
===================================================================================
Title: Pura serverless infra (Lambda + IAM + S3 + API Gateway + CloudWatch) ko
       DECLARATIVE Terraform code me describe karna, ek runnable Python helper se
       Lambda ZIP build karna, .tf resources ko parse karke samajhna, aur dev/prod
       multi-environment deploy + TEARDOWN ke exact commands seekhna.

KYA SEEKHENGE (what concepts):
- DECLARATIVE IaC vs "console clicking" (ClickOps): tum end-state describe karte
  ho, Terraform reality (state) se diff nikaal ke reconcile karta hai. Ek hyphen
  galat console me => "god help you"; code me => review + plan pakad leta hai.
- STATE FILE (.tfstate): Terraform ki "live reality ki samajh". Git me NAHI jaata
  (constantly badalta + secrets). Teams remote backend (S3 + DynamoDB lock) use
  karti hain. (L50/L51)
- PLAN-BEFORE-APPLY: `terraform plan` ek dry-run diff dikhata hai apply se pehle --
  production me non-negotiable. (L50)
- MULTI-ENVIRONMENT via tfvars: ek hi main.tf, alag values (dev.tfvars/prod.tfvars)
  => dev/test/prod parallel, isolated. (L52/L54)
- TEARDOWN via `terraform destroy`: orphaned resources = silent cost. State jaanta
  hai usne kya banaya, isliye exactly wahi clean karta hai (S3 auto-empty bhi). (L55)
- Aur ek REAL deployable Lambda handler (API-Gateway-proxy contract) jo IS lab ke
  Terraform se deploy hota hai -- with a local self-demo (mock events).

KAISE CHALANA (how to run) — CWD = repo root:
    # Default: self-demo. Lambda zip banata hai, .tf resources parse+summarize
    # karta hai, terraform commands print karta hai, mock-event se handler invoke
    # karta hai. Bina AWS / bina key ke chalta hai aur EXIT 0.
    uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab4_terraform_iac.py

LECTURE MAPPING: Ed Donner "AI Engineer Production Track", Week 2 · Day 4.
  L50 = IaC + Terraform intro (provider/variable/resource/state/output/workspace;
        init/apply/destroy; "ek hyphen galat = god help you"; state git-ignored).
  L51 = versions.tf / variables.tf / main.tf (IAM role, S3, Lambda, API Gateway).
  L52 = terraform.tfvars defaults + deploy.sh shell script (build->init->workspace
        ->apply->frontend env inject->S3 sync); Terraform != code editor.
  L53 = outputs.tf + `terraform init` (once) + `./scripts/deploy.sh dev` -> full
        env live; verify Lambda env vars + S3 memory blob.
  L54 = multi-environment dev/test/prod (same script, alag workspace/tfvars).
  L55 = `destroy.sh` / `terraform destroy` teardown; domain survives, infra gaya.

COST: Is lab ko LOCALLY chalana = $0. Yeh helper terraform RUN nahi karta (terraform
  install bhi nahi hai yahan) -- sirf zip banata hai (offline, free) + commands
  teach karta hai. Agar tum REAL me runbook follow karke deploy karoge:
  AWS serverless free-tier udar hai -- Lambda free tier (~1M req/mo), S3 paise ke
  fraction me, API Gateway HTTP API saste, CloudWatch logs minimal. Bedrock Nova
  micro/pro per-token (cents) lagta hai. Ed ka pura course estimate ~$5-$10
  (zyaadatar free), plus optional domain ~$15/year. SABSE BADI cost-safety:
  `terraform destroy` se sab clean kar do => idle/orphaned resources ka silent
  bill khatam (L55).
"""

import json
import os
import re
import sys
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# get_client: provider ke hisaab se (client, model_name). Default groq => free.
# Yeh sirf "Bedrock LLM" wale local fallback ke liye hai (jab AWS na ho to hum
# groq se LLM call ka shape dikha sakte hain). NOTE the `or "placeholder"`:
# OpenAI() None api_key par CONSTRUCTION time hi crash karta hai, isliye placeholder.
# ---------------------------------------------------------------------------
def get_client(provider: str = "groq"):
    """(client, model). Default groq => free, OpenAI-compatible."""
    # Lazy imports: yeh top-level pe rakhne se file import hote hi dotenv/openai
    # load ho jaate -- theek hai (project deps me hain), par hum defensive rehte
    # hain kyunki self-demo ko bina kisi network/key ke chalna hai.
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv(override=True)
    if provider == "groq":
        return OpenAI(base_url="https://api.groq.com/openai/v1",
                      api_key=os.getenv("GROQ_API_KEY") or "placeholder"), "llama-3.3-70b-versatile"
    if provider == "gemini":
        return OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                      api_key=os.getenv("GOOGLE_API_KEY") or "placeholder"), "gemini-2.5-flash"
    raise ValueError(f"Unknown provider: {provider}")


# Paths -- is file ke relative. Terraform folder aur build/ yahin ke paas hain.
HERE = Path(__file__).resolve().parent
TERRAFORM_DIR = HERE / "terraform"
BUILD_DIR = HERE / "build"
LAMBDA_ZIP = BUILD_DIR / "lambda.zip"


# ===========================================================================
# ###############  REAL DEPLOYABLE LAMBDA HANDLER  ##########################
# ===========================================================================
# Yahi function Terraform deploy karta hai (var.lambda_handler =
# "lab4_terraform_iac.handler"). API-Gateway-proxy contract follow karta hai:
#   - event["httpMethod"] / event["path"]  (REST v1 proxy shape), YA
#   - event["requestContext"]["http"]["method"/"path"]  (HTTP API v2 shape)
#   - body ek JSON string hota hai (event["body"]) -- parse karna padta hai.
# Return MUST be: {"statusCode": int, "headers": {...}, "body": json.dumps(...)}.
#
# Memory (S3) aur LLM (Bedrock) dono GRACEFULLY DEGRADE karte hain:
#   - boto3 missing ya AWS creds nahi => LOCAL FILESYSTEM ko S3 ki tarah use karo.
#   - Bedrock available nahi => groq get_client se LLM shape dikhao (ya skip).
# Isliye yeh handler local self-demo me bhi chalta hai aur cloud me bhi.
# ===========================================================================
def _extract_method_and_path(event: dict) -> tuple:
    """Dono proxy shapes (v1 httpMethod, v2 requestContext.http) se method+path nikaalo."""
    # v1 (REST proxy): top-level "httpMethod" / "path".
    method = event.get("httpMethod")
    path = event.get("path")
    if method is None:
        # v2 (HTTP API): requestContext.http.{method,path}.
        http_ctx = (event.get("requestContext") or {}).get("http") or {}
        method = http_ctx.get("method", "GET")
        path = http_ctx.get("path", path or "/")
    return method, (path or "/")


def _read_memory(conversation_id: str) -> list:
    """Conversation history laao. Pehle S3 (agar boto3 + creds), warna local file."""
    # --- AWS path: boto3 LAZILY import. Missing => ImportError => local fallback ---
    try:
        import boto3  # noqa: F401  (sirf availability check)
        bucket = os.getenv("MEMORY_BUCKET")
        if bucket:
            try:
                s3 = boto3.client("s3")
                obj = s3.get_object(Bucket=bucket, Key=f"{conversation_id}.json")
                return json.loads(obj["Body"].read())
            except Exception:
                # Bucket/object nahi mila ya creds galat -- empty history, crash nahi.
                return []
    except ImportError:
        # boto3 hai hi nahi (hamara local env) -- niche local fallback.
        pass

    # --- LOCAL FALLBACK: build/memory/<id>.json ko S3 ki tarah treat karo ---
    local_path = BUILD_DIR / "memory" / f"{conversation_id}.json"
    if local_path.exists():
        return json.loads(local_path.read_text())
    return []


def _write_memory(conversation_id: str, history: list) -> str:
    """History persist karo. S3 (agar mil jaaye) warna local file. Return: kahan likha."""
    payload = json.dumps(history)
    try:
        import boto3
        bucket = os.getenv("MEMORY_BUCKET")
        if bucket:
            try:
                s3 = boto3.client("s3")
                s3.put_object(Bucket=bucket, Key=f"{conversation_id}.json",
                              Body=payload.encode("utf-8"))
                return f"s3://{bucket}/{conversation_id}.json"
            except Exception:
                pass  # creds/bucket issue -- local par gir jao.
    except ImportError:
        pass

    local_dir = BUILD_DIR / "memory"
    local_dir.mkdir(parents=True, exist_ok=True)
    (local_dir / f"{conversation_id}.json").write_text(payload)
    return str(local_dir / f"{conversation_id}.json")


def _generate_reply(prompt: str) -> dict:
    """LLM se reply. Bedrock available ho to wo, warna groq, warna shape-only degrade."""
    # --- Try Bedrock (boto3) -- yeh "real cloud" path hai (L46/L47/L48) ---
    try:
        import boto3
        # creds present? Agar Bedrock call try karein aur fail ho to gracefully girenge.
        if os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE"):
            try:
                client = boto3.client("bedrock-runtime")
                model_id = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-micro-v1:0")
                resp = client.converse(
                    modelId=model_id,
                    messages=[{"role": "user", "content": [{"text": prompt}]}],
                )
                text = resp["output"]["message"]["content"][0]["text"]
                return {"reply": text, "source": f"bedrock:{model_id}"}
            except Exception as e:
                return {"reply": None, "source": "bedrock-error",
                        "note": f"Bedrock call fail ({type(e).__name__}) -> degraded."}
    except ImportError:
        pass  # boto3 nahi -- niche groq/skip.

    # --- LOCAL fallback: groq (free) -- sirf agar key ho ---
    if os.getenv("GROQ_API_KEY"):
        try:
            client, model = get_client("groq")
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=128,
            )
            return {"reply": resp.choices[0].message.content, "source": f"groq:{model}"}
        except Exception as e:
            return {"reply": None, "source": "groq-error",
                    "note": f"groq call fail ({type(e).__name__}) -> degraded."}

    # --- No AWS, no key: shape-only degrade (crash nahi, exit 0 safe) ---
    return {
        "reply": None,
        "source": "no-llm-configured",
        "note": "AWS Bedrock nahi + GROQ_API_KEY nahi => live call skip. Yeh response "
                "SHAPE hai; key/creds set karne par yahan asli reply aayega.",
    }


def handler(event, context):
    """AWS Lambda + API-Gateway-proxy entrypoint. Same function jo Terraform deploy karta hai.

    Routes (app khud route karta hai, gateway $default catch-all):
      GET  /health    -> liveness + config visibility (no LLM, no cost).
      POST /chat      -> {prompt, conversation_id?} => reply + memory append.
    """
    method, path = _extract_method_and_path(event)

    # Common CORS/content headers -- browser ke liye (L45 CORS lesson).
    headers = {"content-type": "application/json", "access-control-allow-origin": "*"}

    # --- GET /health: koi LLM/cost nahi. Platform isse poll karke health check karta. ---
    if path.rstrip("/").endswith("health") or path == "/health":
        body = {
            "status": "ok",
            "environment": os.getenv("ENVIRONMENT", "local"),
            "use_s3": os.getenv("USE_S3", "false"),
            # bool() => sirf True/False expose, kabhi actual value/secret nahi.
            "memory_bucket_configured": bool(os.getenv("MEMORY_BUCKET")),
            "bedrock_model_id": os.getenv("BEDROCK_MODEL_ID", "(unset)"),
        }
        return {"statusCode": 200, "headers": headers, "body": json.dumps(body)}

    # --- POST /chat: asli kaam. body JSON string hota hai -> parse. ---
    if method == "POST":
        # body parse: garbage-in guard. Galat JSON => 400, crash nahi.
        raw = event.get("body") or "{}"
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            return {"statusCode": 400, "headers": headers,
                    "body": json.dumps({"error": "body must be valid JSON"})}

        prompt = (data or {}).get("prompt")
        if not prompt:
            return {"statusCode": 400, "headers": headers,
                    "body": json.dumps({"error": "'prompt' required"})}

        conversation_id = (data or {}).get("conversation_id", "default")

        # 1) memory load (S3 ya local fallback).
        history = _read_memory(conversation_id)
        history.append({"role": "user", "content": prompt})

        # 2) LLM reply (Bedrock -> groq -> shape-only degrade).
        gen = _generate_reply(prompt)
        if gen.get("reply") is not None:
            history.append({"role": "assistant", "content": gen["reply"]})

        # 3) memory persist (S3 ya local fallback).
        stored_at = _write_memory(conversation_id, history)

        body = {
            "conversation_id": conversation_id,
            "reply": gen.get("reply"),
            "llm_source": gen.get("source"),
            "memory_stored_at": stored_at,
            "turns": len(history),
        }
        if gen.get("note"):
            body["note"] = gen["note"]
        return {"statusCode": 200, "headers": headers, "body": json.dumps(body)}

    # --- Anything else: 404 (clean contract). ---
    return {"statusCode": 404, "headers": headers,
            "body": json.dumps({"error": f"no route for {method} {path}"})}


# ===========================================================================
# (a) PACKAGER -- handler file ko build/lambda.zip me zip karo (REAL, offline).
# ===========================================================================
def build_lambda_zip(handler_file: Path = None) -> Path:
    """handler_file ko ek Lambda deployment zip me pack karo. Bilkul offline, free.

    Yahi `uv run deploy.py` ka role hai jo Ed ke deploy.sh me hota tha (L52): infra
    se PEHLE artifact build hota hai. Terraform phir is zip ko `filename` se deploy
    karta hai (main.tf -> aws_lambda_function.api).
    """
    handler_file = handler_file or Path(__file__).resolve()
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    # zipfile => Python stdlib, koi external dep nahi => guaranteed offline-runnable.
    # ZIP_DEFLATED => compress (chhota artifact = tezz upload). Lambda zip me file
    # ka naam wahi hona chahiye jo handler "<module>.<function>" me module hai.
    with zipfile.ZipFile(LAMBDA_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        # arcname = zip ke andar ka naam. handler "lab4_terraform_iac.handler"
        # expect karta hai file "lab4_terraform_iac.py".
        zf.write(handler_file, arcname=handler_file.name)

    size_kb = LAMBDA_ZIP.stat().st_size / 1024
    print(f"[packager] Built {LAMBDA_ZIP.relative_to(HERE)}  ({size_kb:.1f} KB)")
    print(f"[packager] Zip ke andar: {handler_file.name}  "
          f"=> Lambda handler '{handler_file.stem}.handler' isse match karta hai.")
    return LAMBDA_ZIP


# ===========================================================================
# (b) PARSER -- .tf files se `resource "type" "name"` scan karke summary do.
# ===========================================================================
# Simple regex scan -- HCL ka full parser nahi (woh overkill). Hum sirf resource/
# data/variable/output/provider blocks count + list karte hain taaki reader ko
# "is stack me kya-kya declared hai" ka human summary mil jaaye.
_RESOURCE_RE = re.compile(r'^\s*resource\s+"([^"]+)"\s+"([^"]+)"', re.MULTILINE)
_DATA_RE = re.compile(r'^\s*data\s+"([^"]+)"\s+"([^"]+)"', re.MULTILINE)
_VAR_RE = re.compile(r'^\s*variable\s+"([^"]+)"', re.MULTILINE)
_OUT_RE = re.compile(r'^\s*output\s+"([^"]+)"', re.MULTILINE)

# Friendly Hinglish "yeh resource kya karta hai" mapping -- teaching ke liye.
_WHY = {
    "aws_lambda_function": "Serverless compute -- humara deployable handler chalata hai.",
    "aws_iam_role": "Lambda kaun ban sakta hai + kya kar sakta hai (trust).",
    "aws_iam_role_policy": "Least-privilege permissions (logs + IS env ka S3).",
    "aws_s3_bucket": "Conversation memory persist (stateless Lambda ke bahar).",
    "aws_s3_bucket_public_access_block": "Memory bucket ko public hone se rokta hai (security).",
    "aws_s3_bucket_versioning": "Galti se overwrite/delete par recover ho sake.",
    "aws_cloudwatch_log_group": "Lambda ke logs ka ghar (retention => cost control).",
    "aws_apigatewayv2_api": "Internet se Lambda tak HTTP front-door.",
    "aws_apigatewayv2_integration": "API ko Lambda se jodta hai (AWS_PROXY).",
    "aws_apigatewayv2_route": "Konsa path Lambda par jaaye ($default catch-all).",
    "aws_apigatewayv2_stage": "Deployed version ka URL segment (auto_deploy).",
    "aws_lambda_permission": "API Gateway ko Lambda invoke karne ki ijaazat.",
}


def parse_terraform(tf_dir: Path = TERRAFORM_DIR) -> dict:
    """Saari *.tf files padho aur resources/data/variables/outputs ka summary lauta do."""
    summary = {"resources": [], "data_sources": [], "variables": [], "outputs": [],
               "files": [], "found_dir": tf_dir.exists()}
    if not tf_dir.exists():
        return summary

    for tf_file in sorted(tf_dir.glob("*.tf")):
        text = tf_file.read_text()
        summary["files"].append(tf_file.name)
        summary["resources"] += [(t, n) for t, n in _RESOURCE_RE.findall(text)]
        summary["data_sources"] += [(t, n) for t, n in _DATA_RE.findall(text)]
        summary["variables"] += _VAR_RE.findall(text)
        summary["outputs"] += _OUT_RE.findall(text)
    return summary


def print_terraform_summary(summary: dict) -> None:
    """parse_terraform ka human-friendly Hinglish print."""
    print("=" * 72)
    print("PARSED TERRAFORM RESOURCES  (regex scan of terraform/*.tf)")
    print("=" * 72)
    if not summary["found_dir"]:
        print("[!] terraform/ folder nahi mila -- skip.")
        return

    print(f"Files scanned: {', '.join(summary['files'])}\n")

    print(f"RESOURCES ({len(summary['resources'])}) -- yeh AWS par BANENGE:")
    for rtype, rname in summary["resources"]:
        why = _WHY.get(rtype, "")
        print(f"  - {rtype:38s} \"{rname}\"")
        if why:
            print(f"        WHY: {why}")
    print()

    print(f"DATA SOURCES ({len(summary['data_sources'])}) -- read-only lookups (banate nahi):")
    for dtype, dname in summary["data_sources"]:
        print(f"  - {dtype} \"{dname}\"")
    print()

    print(f"VARIABLES ({len(summary['variables'])}) -- tfvars se values aati hain:")
    print("  " + ", ".join(summary["variables"]))
    print()

    print(f"OUTPUTS ({len(summary['outputs'])}) -- apply ke baad bahar aati hain:")
    print("  " + ", ".join(summary["outputs"]))
    print()


# ===========================================================================
# (c) COMMAND TEACHER -- exact terraform init/plan/apply/destroy commands.
# ===========================================================================
# Yeh helper terraform RUN nahi karta (install nahi hai + we don't touch AWS).
# Sirf EXACT commands print karta hai jo runbook me chalengi -- teaching.
def print_terraform_commands() -> None:
    """dev + prod ke liye exact terraform lifecycle commands print karo (no execution)."""
    print("=" * 72)
    print("TERRAFORM COMMANDS  (yeh helper RUN nahi karta -- sirf teach karta hai)")
    print("=" * 72)
    print("Pehle artifact build (ye helper ne abhi kiya): build/lambda.zip ready.")
    print("Phir terraform/ folder me ja ke:\n")

    print("  # 0) ek baar: providers download + working dir init")
    print("  terraform init\n")

    print("  # --- DEV environment ---")
    print("  # plan = APPLY se PEHLE dry-run diff (kya banega/badlega/mitega).")
    print("  #        Production me yeh dekhe bina apply mat karo (L50).")
    print("  terraform plan  -var-file=dev.tfvars")
    print("  terraform apply -var-file=dev.tfvars\n")

    print("  # --- PROD environment (alag values, same code) ---")
    print("  terraform plan  -var-file=prod.tfvars")
    print("  terraform apply -var-file=prod.tfvars\n")

    print("  # outputs read (deploy script ise frontend me inject karta -- L52/L53):")
    print("  terraform output -raw api_endpoint\n")

    print("  # --- TEARDOWN (cost-safety! L55) -- jo banaya wahi clean ---")
    print("  # Terraform S3 buckets pehle KHUD empty karta hai, phir destroy.")
    print("  # Orphaned/idle resources = silent bill => khatam karne ke liye:")
    print("  terraform destroy -var-file=dev.tfvars")
    print("  terraform destroy -var-file=prod.tfvars\n")

    print("NOTE: real teams `.tfstate` git me NAHI daalte (badalta + secrets) --")
    print("      remote backend (S3 + DynamoDB lock) use karti hain (L50/L51).")
    print()


# ===========================================================================
# SELF-DEMO — `uv run <file>` (no args) yahan aata hai. Bina AWS/key -> exit 0.
# ===========================================================================
def _invoke_handler(label: str, event: dict) -> None:
    """Handler ko ek mock API-Gateway-proxy event se call karke response print karo."""
    print(f"--- {label} ---")
    resp = handler(event, context=None)
    print(f"  statusCode = {resp['statusCode']}")
    # body ek JSON string hai (proxy contract) -- pretty print for readability.
    try:
        parsed = json.loads(resp["body"])
        print("  body       = " + json.dumps(parsed, indent=2, ensure_ascii=False))
    except Exception:
        print(f"  body       = {resp['body']}")
    print()


def run_self_demo() -> None:
    """Packager + parser + commands + mock handler invokes. Hamesha exit 0."""
    print("\n" + "#" * 72)
    print("#  LAB 4 SELF-DEMO — Infrastructure as Code with Terraform")
    print("#" * 72 + "\n")

    # --- (a) Build the Lambda zip (REAL, offline) -----------------------
    print("=" * 72)
    print("(a) PACKAGE LAMBDA  -- handler ko build/lambda.zip me zip karo")
    print("=" * 72)
    build_lambda_zip()
    print()

    # --- (b) Parse + summarize the .tf files ----------------------------
    summary = parse_terraform()
    print_terraform_summary(summary)

    # --- (c) Print the terraform commands (teach, don't run) ------------
    print_terraform_commands()

    # --- (d) Invoke the REAL handler with mock proxy events -------------
    print("=" * 72)
    print("(d) LOCAL HANDLER INVOKE  -- mock API-Gateway-proxy events")
    print("    (no boto3 / no AWS / no key => graceful local fallback)")
    print("=" * 72)

    # Demo ko DETERMINISTIC rakho: pichhli run ka local-fallback memory file hata
    # do, taaki turn counts hamesha 1 phir 2 dikhein (warna re-run par badhte
    # rehte). Real S3 me yeh persist hota -- yeh sirf demo hygiene hai.
    _demo_mem = BUILD_DIR / "memory" / "demo.json"
    if _demo_mem.exists():
        _demo_mem.unlink()

    # GET /health (v2 HTTP API shape) -- no LLM, no cost.
    _invoke_handler("GET /health", {
        "requestContext": {"http": {"method": "GET", "path": "/health"}},
    })

    # POST /chat (v1 REST proxy shape) -- memory + LLM (degrades gracefully).
    _invoke_handler("POST /chat  (turn 1)", {
        "httpMethod": "POST",
        "path": "/chat",
        "body": json.dumps({"prompt": "Hi, my name is Alex.",
                            "conversation_id": "demo"}),
    })

    # POST /chat turn 2 -- memory persist hua, turns badhna chahiye.
    _invoke_handler("POST /chat  (turn 2, same conversation)", {
        "httpMethod": "POST",
        "path": "/chat",
        "body": json.dumps({"prompt": "What did I just say my name was?",
                            "conversation_id": "demo"}),
    })

    print("#" * 72)
    print("#  LAB 4 complete. Declarative IaC: ek code -> dev/prod parallel.")
    print("#  Build zip -> terraform plan -> apply -> (verify) -> destroy.")
    print("#  State git-ignored; plan-before-apply; destroy = cost-safety.")
    print("#" * 72 + "\n")

    # Hamesha clean exit 0 -- chaahe AWS/boto3/key ho ya na ho.
    raise SystemExit(0)


if __name__ == "__main__":
    # Default (aur --demo): self-demo. Koi AWS/key zaroori nahi => exit 0.
    if len(sys.argv) == 1 or "--demo" in sys.argv:
        run_self_demo()
    elif "--build" in sys.argv:
        # Sirf zip banao (CI/deploy script use kar sakta hai).
        build_lambda_zip()
    else:
        print("Usage: lab4_terraform_iac.py [--demo | --build]")
        run_self_demo()
