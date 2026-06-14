"""
LAB 6 — Serverless COST CONTROL + OBSERVABILITY (resource management)
=====================================================================
Title: Ek runnable cost/observability "control plane" — serverless ka paisa kahan
       jaata hai estimate karna, CloudWatch-style metrics emit karna, aur ek
       CostGuard se runaway spend ko app-level par BLOCK karna. NO AWS needed.

KYA SEEKHENGE (what concepts):
- WHERE SERVERLESS MONEY GOES: Lambda (requests + GB-seconds compute), S3 (storage +
  requests), API Gateway (per-million requests), CloudWatch (logs ingest + custom
  metrics), aur Bedrock (per-1k-TOKEN, input vs output) — yahi 5 lines tumhara
  monthly bill banati hain. Hum ek itemized BUDGET REPORT print karte hain.
- FREE-TIER limits: AWS har service par kuch monthly free deta hai (e.g. Lambda
  1M requests + 400k GB-s, API Gateway 1M calls, CloudWatch 5GB logs). Estimator
  in deductions ko line-by-line note karta hai — taaki tumhe pata ho kab paid
  zone shuru hota hai (L63 ka "billing & cost management" healthy habit).
- CLOUDWATCH METRICS -> ALARMS -> BUDGET ALERTS: jo measure nahi hota wo control
  nahi hota (L49). emit_metric() structured JSON (EMF-ish) print karta hai jo
  CloudWatch metric ban jaata; us metric par tum ALARM (e.g. TokensPerHour > X)
  laga ke SNS/email notification paa sakte ho — runaway cost detect karne ka
  sabse sasta tareeka.
- CostGuard (THE KEY LESSON): AWS me koi HARD SPEND CAP nahi hai (Budgets sirf
  *alert* karta hai, paisa rokta nahi). Ek bug/abuse/loop bill ko blow kar sakta
  hai. Isliye DEFENCE app ke andar honi chahiye: per-day REQUEST cap + per-call
  max_tokens cap. CostGuard ek wrapper hai jo limit cross hone par call ko BLOCK
  kar deta hai (raise) — yeh tumhara real circuit-breaker hai.
- DEPLOYABLE handler: ek asli `handler(event, context)` (Lambda + API-Gateway-proxy
  contract) jo /estimate aur /metric endpoints expose karta — wahi function jo
  deploy hota.

KAISE CHALANA (how to run) — CWD = repo root:
    # Default: self-demo (estimates + metrics + CostGuard block + handler invokes), exit 0
    uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab6_cost_control_observability.py

Yeh lab LOCAL hai — boto3/AWS creds/LLM key kuch bhi NAHI chahiye. Agar boto3 +
AWS creds present ho to CloudWatch ko real metric bhejne ka path bhi hai (lazy
import, try/except); warna saaf Hinglish "AWS not configured -> local fallback"
print karke local stdout par emit karta hai. Bilkul crash/hang nahi.

LECTURE MAPPING: Ed Donner "AI Engineer Production Track", Week 2 (AWS Serverless).
  L49 = Monitoring with CloudWatch + Bedrock metrics (invocations, input/output
        token count, latency; Lambda invocations/duration/errors; dashboards).
        => yahan emit_metric() un metrics ko EMF JSON me banata + metrics->alarms
           ka mental model deta.
  L63 = Day 5 Resource Management & Cost Control (Resource Explorer, destroy
        workflow, Billing & Cost Management ko regularly dekhna, "tiny charges
        bhi add up"). => yahan estimator monthly budget report + CostGuard yahi
        FinOps discipline ko CODE me daalta.

COST: Is lab ko LOCALLY chalana = $0 (sirf Python, koi network/AWS call nahi).
  Jo bill yeh estimate karta hai wo us "twin"-style serverless stack ka hai jo
  runbook me deploy hota: low traffic par AWS free-tier ke andar aksar ~$0; Bedrock
  token cost + thoda Lambda/CloudWatch ke saath chhota stack typically ~$1-$10/month.
  Asli paisa ZYAADA traffic + bade Bedrock token volumes par lagta — isiliye
  max_tokens cap + request cap (CostGuard) + budget alarms pehli line of defence.
"""

import json
import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv
from openai import OpenAI

# .env load — override=True (Ed Donner convention): .env shell ki purani value ko
# jeet jaata hai. Is lab me LLM optional hai, par convention consistent rakhte hain.
load_dotenv(override=True)


# ---------------------------------------------------------------------------
# get_client: provider -> (client, model). Is lab me LLM strictly OPTIONAL hai
# (estimator/metrics/guard sab pure-Python hain). Helper isliye rakha hai taaki
# Bedrock-fallback path (LLM via groq) demonstrate kar saken bina key ke crash kiye.
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


# ===========================================================================
# ###############  PART 1 — PRICING TABLE + FREE-TIER LIMITS  ###############
# ===========================================================================
# Yeh numbers us-east-1 ke roughly representative on-demand rates hain (2025-ish).
# IMPORTANT: ye ESTIMATE ke liye hain, exact billing ke liye nahi — region/tier ke
# saath badalte hain. Production me tum AWS Pricing API ya Cost Explorer se exact
# numbers laate ho. Yahan goal: tujhe SHAPE samajhana ki paisa kahan jaata hai.
#
# Sab rate ek dict me ek hi jagah — taaki "money kahan jaata hai" ek nazar me dikhe.
# ---------------------------------------------------------------------------
PRICING = {
    # --- Lambda: do alag charges ---
    # 1) Per-REQUEST: har invocation par flat fee.
    "lambda_per_request": 0.20 / 1_000_000,          # $0.20 per 1M requests
    # 2) Per-COMPUTE: GB-seconds = (memory_GB) * (duration_seconds) * num_requests.
    #    Yahi aksar bada part hota hai (L49 ka "Billed Duration" yahin charge hota).
    "lambda_per_gb_second": 0.0000166667,            # $/GB-second

    # --- API Gateway (HTTP API): per-million requests ---
    "apigw_per_request": 1.00 / 1_000_000,           # $1.00 per 1M requests (HTTP API)

    # --- S3: storage (per GB-month) + request charges (PUT/GET) ---
    "s3_storage_per_gb_month": 0.023,                # $/GB-month (Standard)
    "s3_put_per_request": 0.005 / 1_000,             # $0.005 per 1k PUT/COPY/POST
    "s3_get_per_request": 0.0004 / 1_000,            # $0.0004 per 1k GET

    # --- CloudWatch: logs ingestion (per GB) + custom metrics (per metric/month) ---
    "cw_logs_per_gb": 0.50,                          # $0.50 per GB ingested
    "cw_custom_metric_per_month": 0.30,              # $0.30 per custom metric/month

    # --- Bedrock (Amazon Nova Lite-ish): per-1k-TOKEN, input sasta, output mehenga.
    #     L49 me dekha tha: input token count >> output token count (system+history
    #     bada, jawab chhota), par OUTPUT ka per-token rate mehenga hota hai. ---
    "bedrock_input_per_1k": 0.00006,                 # $/1k input tokens
    "bedrock_output_per_1k": 0.00024,                # $/1k output tokens
}

# FREE-TIER (monthly) — AWS in tak free deta hai; estimator inhe DEDUCT karta hai.
# (Note: kuch free-tiers "12 months only" hote hain, kuch "always free" — yahan
# simplify karke monthly allowance treat kar rahe hain, teaching ke liye.)
FREE_TIER = {
    "lambda_requests": 1_000_000,        # 1M requests/month free
    "lambda_gb_seconds": 400_000,        # 400,000 GB-s/month free
    "apigw_requests": 1_000_000,         # 1M HTTP API calls/month free (first 12mo)
    "cw_logs_gb": 5.0,                   # 5 GB logs ingestion free
    # S3 free-tier (5GB) "12 months only" hota hai; conservative rehne ke liye hum
    # S3 par free-tier deduct NAHI karte (worst-case dikhao). Bedrock par koi
    # free-tier nahi — har token paisa (yeh sabse important line of the bill).
}

# Ek "din" me kitne seconds (request/day -> request/month convert karne ke liye)
DAYS_PER_MONTH = 30


# ===========================================================================
# ###################  PART 2 — THE COST ESTIMATOR  ########################
# ===========================================================================
def estimate_monthly_cost(
    requests_per_day: int,
    avg_input_tokens: int = 800,
    avg_output_tokens: int = 150,
    lambda_memory_mb: int = 512,
    lambda_duration_ms: int = 1000,
    s3_storage_gb: float = 1.0,
    log_kb_per_request: float = 2.0,
    custom_metrics: int = 4,
    print_report: bool = True,
):
    """
    requests_per_day se ek itemized MONTHLY budget banata hai (Lambda + API GW +
    S3 + CloudWatch + Bedrock), free-tier deductions ke saath. Ek dict return karta
    hai aur (default) ek human-readable Hinglish report print karta hai.

    Defaults L49 ki real observations se inspired:
      - avg_input_tokens=800, avg_output_tokens=150  (input >> output, jaise twin app)
      - lambda_memory_mb=512, lambda_duration_ms=1000 (~1s, jaisa Nova latency dikha)
    """
    # --- Step 0: per-month volumes nikaalo --------------------------------
    req_month = requests_per_day * DAYS_PER_MONTH

    # ---------------------------------------------------------------------
    # LAMBDA — do hisse: (a) per-request fee, (b) compute (GB-seconds).
    # GB-seconds = memory_in_GB * duration_in_seconds * num_requests.
    # Free-tier: pehle 1M requests + 400k GB-s free; usse upar ka paid.
    # ---------------------------------------------------------------------
    mem_gb = lambda_memory_mb / 1024.0
    dur_s = lambda_duration_ms / 1000.0
    gb_seconds = mem_gb * dur_s * req_month

    # max(0, ...) => free allowance ke andar rahe to paid part 0.
    paid_lambda_requests = max(0, req_month - FREE_TIER["lambda_requests"])
    paid_gb_seconds = max(0.0, gb_seconds - FREE_TIER["lambda_gb_seconds"])
    lambda_request_cost = paid_lambda_requests * PRICING["lambda_per_request"]
    lambda_compute_cost = paid_gb_seconds * PRICING["lambda_per_gb_second"]
    lambda_cost = lambda_request_cost + lambda_compute_cost

    # ---------------------------------------------------------------------
    # API GATEWAY — per-request; pehle 1M free (HTTP API).
    # ---------------------------------------------------------------------
    paid_apigw = max(0, req_month - FREE_TIER["apigw_requests"])
    apigw_cost = paid_apigw * PRICING["apigw_per_request"]

    # ---------------------------------------------------------------------
    # S3 — storage (GB-month) + requests. Maan lo har user-request ~1 PUT
    # (e.g. conversation save) + ~1 GET (history read). Free-tier deduct NAHI
    # (conservative). Chhote stacks par yeh aksar cents me hota hai.
    # ---------------------------------------------------------------------
    s3_storage_cost = s3_storage_gb * PRICING["s3_storage_per_gb_month"]
    s3_put_cost = req_month * PRICING["s3_put_per_request"]
    s3_get_cost = req_month * PRICING["s3_get_per_request"]
    s3_cost = s3_storage_cost + s3_put_cost + s3_get_cost

    # ---------------------------------------------------------------------
    # CLOUDWATCH — logs ingest (GB) + custom metrics (per metric/month).
    # Har request ~log_kb_per_request KB logs likhta (START/END/REPORT + tumhare
    # structured logs). Pehle 5GB free. Custom metrics (jo emit_metric banata)
    # ka apna flat charge — yahi observability ki "keemat" hai (par sasti, aur
    # cost-runaway pakadne me yeh paisa wasool hai).
    # ---------------------------------------------------------------------
    log_gb = (req_month * log_kb_per_request) / (1024.0 * 1024.0)  # KB -> GB
    paid_log_gb = max(0.0, log_gb - FREE_TIER["cw_logs_gb"])
    cw_logs_cost = paid_log_gb * PRICING["cw_logs_per_gb"]
    cw_metrics_cost = custom_metrics * PRICING["cw_custom_metric_per_month"]
    cw_cost = cw_logs_cost + cw_metrics_cost

    # ---------------------------------------------------------------------
    # BEDROCK — per-1k-TOKEN, input vs output alag rate. KOI FREE-TIER NAHI.
    # Yeh aksar LLM app ka SABSE BADA cost hota hai (jab traffic + tokens badhte).
    # Notice: output per-token zyada mehenga => isiliye max_tokens cap critical.
    # ---------------------------------------------------------------------
    input_tokens_month = req_month * avg_input_tokens
    output_tokens_month = req_month * avg_output_tokens
    bedrock_input_cost = (input_tokens_month / 1000.0) * PRICING["bedrock_input_per_1k"]
    bedrock_output_cost = (output_tokens_month / 1000.0) * PRICING["bedrock_output_per_1k"]
    bedrock_cost = bedrock_input_cost + bedrock_output_cost

    total = lambda_cost + apigw_cost + s3_cost + cw_cost + bedrock_cost

    # Structured result — programmatic use ke liye (e.g. budget alert threshold check).
    result = {
        "inputs": {
            "requests_per_day": requests_per_day,
            "requests_per_month": req_month,
            "avg_input_tokens": avg_input_tokens,
            "avg_output_tokens": avg_output_tokens,
            "lambda_memory_mb": lambda_memory_mb,
            "lambda_duration_ms": lambda_duration_ms,
        },
        "line_items": {
            "lambda": round(lambda_cost, 4),
            "api_gateway": round(apigw_cost, 4),
            "s3": round(s3_cost, 4),
            "cloudwatch": round(cw_cost, 4),
            "bedrock": round(bedrock_cost, 4),
        },
        "total_monthly_usd": round(total, 4),
        "free_tier_notes": {
            "lambda_requests_free_used": min(req_month, FREE_TIER["lambda_requests"]),
            "lambda_gb_seconds_used": round(gb_seconds, 1),
            "lambda_gb_seconds_free": FREE_TIER["lambda_gb_seconds"],
            "apigw_requests_free_used": min(req_month, FREE_TIER["apigw_requests"]),
            "cw_logs_gb_used": round(log_gb, 4),
            "cw_logs_gb_free": FREE_TIER["cw_logs_gb"],
            "bedrock_free_tier": "NONE — har token par paisa",
        },
    }

    if print_report:
        _print_estimate_report(result)
    return result


def _print_estimate_report(r: dict):
    """estimate_monthly_cost ka result ek saaf itemized Hinglish budget report me."""
    inp = r["inputs"]
    li = r["line_items"]
    ft = r["free_tier_notes"]
    print("-" * 72)
    print(f"MONTHLY COST ESTIMATE  |  {inp['requests_per_day']:,} req/day "
          f"({inp['requests_per_month']:,} req/month)")
    print(f"  Lambda: {inp['lambda_memory_mb']}MB x {inp['lambda_duration_ms']}ms  |  "
          f"Tokens: ~{inp['avg_input_tokens']} in / {inp['avg_output_tokens']} out per call")
    print("-" * 72)
    # Har line item — aligned. f"{x:>9.4f}" => $ amount right-aligned.
    print(f"  Lambda (req + GB-s compute) .......... ${li['lambda']:>9.4f}")
    print(f"  API Gateway (per request) ............ ${li['api_gateway']:>9.4f}")
    print(f"  S3 (storage + PUT/GET) ............... ${li['s3']:>9.4f}")
    print(f"  CloudWatch (logs + custom metrics) ... ${li['cloudwatch']:>9.4f}")
    print(f"  Bedrock (input + output tokens) ...... ${li['bedrock']:>9.4f}   <- aksar sabse bada")
    print("  " + "-" * 50)
    print(f"  TOTAL (estimated) .................... ${r['total_monthly_usd']:>9.4f} / month")
    print("-" * 72)
    # FREE-TIER notes — taaki pata chale kab paid zone shuru hota hai.
    print("  FREE-TIER deductions (kab paid zone shuru hota hai):")
    print(f"    - Lambda requests : {ft['lambda_requests_free_used']:,} / "
          f"{FREE_TIER['lambda_requests']:,} free use hue")
    print(f"    - Lambda GB-s     : {ft['lambda_gb_seconds_used']:,} used / "
          f"{ft['lambda_gb_seconds_free']:,} free")
    print(f"    - API GW requests : {ft['apigw_requests_free_used']:,} / "
          f"{FREE_TIER['apigw_requests']:,} free use hue")
    print(f"    - CloudWatch logs : {ft['cw_logs_gb_used']} GB used / "
          f"{ft['cw_logs_gb_free']} GB free")
    print(f"    - Bedrock         : {ft['bedrock_free_tier']}")
    print("-" * 72)


# ===========================================================================
# ###############  PART 3 — CLOUDWATCH-STYLE METRIC EMITTER  ###############
# ===========================================================================
# emit_metric() ek structured JSON line print karta hai jo CloudWatch EMF
# (Embedded Metric Format) se milta-julta hai. EMF ka asli kamaal: tum SIRF apne
# Lambda logs me ye JSON likho, aur CloudWatch usse AUTOMATICALLY ek METRIC bana
# leta hai — bina alag PutMetricData API call ke (sasta + fast). Us metric par
# phir tum ALARM laga sakte ho (L49 ka backend-dev note: "Errors>0 ya p99>3s ya
# TokensPerHour>X par SNS notify").
#
# Flow yaad rakho: emit_metric (logs) -> CloudWatch Metric -> Alarm -> SNS/email
#                  -> (aur AWS Budgets se monthly $ threshold par alert).
# Yeh chain hi tumhe runaway cost se bachati hai (kyunki HARD spend cap nahi hota).
# ---------------------------------------------------------------------------
def emit_metric(name: str, value: float, unit: str = "Count",
                namespace: str = "TwinApp", dimensions: dict | None = None,
                use_aws: bool = False):
    """
    Ek metric "emit" karta hai. Default: EMF-style JSON stdout par print (jo Lambda
    me CloudWatch khud metric bana leta). use_aws=True + boto3 + creds ho to real
    PutMetricData karta; warna SAAF Hinglish fallback message ke saath local print.
    NEVER crashes, NEVER hangs.
    """
    dimensions = dimensions or {}

    # --- Optional real-AWS path: LAZY import boto3 (env me hai hi nahi) ----
    # boto3 ya creds missing => local fallback. Yahi mandatory graceful-degrade.
    if use_aws:
        try:
            import boto3  # lazy: top-level import na karo, warna env crash karega
            # Creds ki maujoodgi check — get_credentials() None de to creds nahi hain.
            session = boto3.session.Session()
            if session.get_credentials() is None:
                raise RuntimeError("no AWS credentials")
            cw = session.client("cloudwatch")
            cw.put_metric_data(
                Namespace=namespace,
                MetricData=[{
                    "MetricName": name,
                    "Value": float(value),
                    "Unit": unit,
                    "Dimensions": [{"Name": k, "Value": str(v)}
                                   for k, v in dimensions.items()],
                }],
            )
            print(f"[CloudWatch] PutMetricData OK -> {namespace}/{name}={value} {unit}")
            return {"sent_to": "aws", "name": name, "value": value}
        except ImportError:
            print("[INFO] boto3 missing => AWS not configured -> local fallback "
                  "(EMF JSON stdout). pip/uv add boto3 + AWS creds for real send.")
        except Exception as e:  # creds missing, network, perms — kuch bhi
            print(f"[INFO] AWS not configured ({e}) -> local fallback (EMF JSON stdout).")

    # --- Local fallback: EMF-ish JSON line (default path) -----------------
    # CloudWatch EMF schema ka simplified shape. Asli EMF me "_aws" block hota hai
    # jisme CloudWatchMetrics + Timestamp; baaki keys flat metric values hoti hain.
    emf = {
        "_aws": {
            "CloudWatchMetrics": [{
                "Namespace": namespace,
                "Dimensions": [list(dimensions.keys())] if dimensions else [[]],
                "Metrics": [{"Name": name, "Unit": unit}],
            }],
        },
        name: value,
        **dimensions,  # dimensions ko top-level keys ke roop me bhi (EMF requirement)
    }
    # json.dumps ek single line — yeh wahi format hai jo Lambda log me jaata.
    print("[EMF] " + json.dumps(emf))
    return {"sent_to": "local_emf", "name": name, "value": value}


# ===========================================================================
# ####################  PART 4 — THE CostGuard PATTERN  ####################
# ===========================================================================
# YEH IS LAB KA DIL HAI (L63 cost-control). Yaad rakho:
#   AWS me koi HARD SPEND CAP nahi hai. AWS Budgets sirf *alert* bhejta hai —
#   paisa nahi rokta. Ek infinite loop / abuse / runaway agent raat-bhar me bill
#   blow kar sakta hai. Isliye defence APP ke andar honi chahiye:
#     1) per-DAY REQUEST cap  -> total invocations bound karta (Lambda+Bedrock cost)
#     2) per-CALL max_tokens cap -> ek single call ki worst-case Bedrock cost bound
#   CostGuard ek wrapper hai: limit cross hone par call ko BLOCK kar deta (raise),
#   aur har decision par ek metric emit karta (taaki alarm laga sako).
# ---------------------------------------------------------------------------
class CostGuardError(Exception):
    """CostGuard ne ek call ko BLOCK kiya — limit exceed (request cap ya token cap)."""


@dataclass
class CostGuard:
    """
    Per-day request cap + per-call max_tokens cap enforce karta hai. allow()
    har incoming call ke liye call karo — agar safe hai to True, warna
    CostGuardError raise karke call ko BLOCK karta hai.

    NOTE: yeh ek SINGLE-PROCESS in-memory counter hai (teaching ke liye). Lambda
    stateless + multi-instance hota hai, isliye PRODUCTION me ye counter DynamoDB
    ya Redis (shared store) me rakha jaata. Pattern wahi rehta — sirf storage
    badalta. Yahan local counter se concept saaf dikhta hai.
    """
    max_requests_per_day: int = 1000      # per-day REQUEST cap (volume brake)
    max_tokens_per_call: int = 512        # per-CALL token cap (single-call brake)
    _used_today: int = field(default=0)   # aaj ab tak kitne allow hue (internal)

    def allow(self, requested_max_tokens: int) -> bool:
        """
        Ek call ko safe hone par allow karta (True). Warna metric emit karke
        CostGuardError raise karta (BLOCK). Do guard:
          (a) requested_max_tokens > per-call cap   -> block (single call too big)
          (b) _used_today >= per-day request cap     -> block (daily volume hit)
        """
        # --- Guard (a): per-call token cap ---------------------------------
        # Output tokens sabse mehenge — isliye ek single call ka token budget bound.
        if requested_max_tokens > self.max_tokens_per_call:
            # Block ko bhi MEASURE karo => is metric par alarm laga sakte ho.
            emit_metric("CostGuardBlocked", 1, unit="Count",
                        dimensions={"reason": "max_tokens_exceeded"})
            raise CostGuardError(
                f"BLOCKED: max_tokens={requested_max_tokens} > cap "
                f"{self.max_tokens_per_call}. Per-call token cap teri single-call "
                f"Bedrock cost ko bound karta hai (output tokens sabse mehenge)."
            )

        # --- Guard (b): per-day request cap --------------------------------
        if self._used_today >= self.max_requests_per_day:
            emit_metric("CostGuardBlocked", 1, unit="Count",
                        dimensions={"reason": "daily_request_cap"})
            raise CostGuardError(
                f"BLOCKED: aaj ka request cap {self.max_requests_per_day} hit ho gaya "
                f"({self._used_today} use hue). AWS hard spend cap nahi deta — yeh "
                f"app-level brake hi tujhe runaway bill se bachata hai."
            )

        # --- Allowed: counter badhao + ek allowed-metric emit karo ----------
        self._used_today += 1
        emit_metric("CostGuardAllowed", 1, unit="Count",
                    dimensions={"used_today": str(self._used_today)})
        return True


# ===========================================================================
# ##############  PART 5 — DEPLOYABLE LAMBDA HANDLER (real)  ###############
# ===========================================================================
# Yeh wahi function hai jo AWS Lambda + API-Gateway-proxy ke peeche DEPLOY hota.
# Contract: event["httpMethod"], event["path"], event["body"] (JSON string) padho;
# return {"statusCode": int, "headers": {...}, "body": json.dumps(...)}.
# Do routes:
#   GET  /estimate?requests_per_day=...   -> monthly cost estimate (JSON)
#   POST /metric  {name,value,unit}       -> ek metric emit karo (EMF/local)
# Ek module-level CostGuard se hum har invocation ko bhi guard karte (demo).
# ---------------------------------------------------------------------------
_HANDLER_GUARD = CostGuard(max_requests_per_day=1000, max_tokens_per_call=512)


def handler(event, context):
    """AWS Lambda entrypoint (API-Gateway-proxy contract). Local self-demo ise
    hand-built mock events ke saath call karta — wahi function deploy hota."""
    method = (event or {}).get("httpMethod", "GET")
    path = (event or {}).get("path", "/")

    # JSON helper — har response ko consistent shape me wrap karta. CORS header
    # bhi taaki browser frontend (CloudFront) se call ho sake (L45 CORS lesson).
    def _resp(status: int, payload: dict):
        return {
            "statusCode": status,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(payload),
        }

    try:
        # --- ROUTE: GET /estimate -----------------------------------------
        if method == "GET" and path == "/estimate":
            # query string params API-GW proxy event me yahan aate hain.
            qs = (event.get("queryStringParameters") or {})
            rpd = int(qs.get("requests_per_day", 1000))
            # print_report=False => handler clean JSON deta (server me prints noise).
            est = estimate_monthly_cost(rpd, print_report=False)
            # Har estimate par ek metric emit — taaki "EstimatedMonthlyUSD" track ho
            # aur us par budget-style alarm laga sako.
            emit_metric("EstimatedMonthlyUSD", est["total_monthly_usd"], unit="None",
                        dimensions={"requests_per_day": str(rpd)})
            return _resp(200, est)

        # --- ROUTE: POST /metric ------------------------------------------
        if method == "POST" and path == "/metric":
            body = json.loads(event.get("body") or "{}")
            name = body.get("name", "CustomMetric")
            value = float(body.get("value", 0))
            unit = body.get("unit", "Count")
            # CostGuard: yeh ek "call" hai — per-day cap check (token cap N/A yahan,
            # to ek chhota value pass karte taaki token-guard trigger na ho).
            _HANDLER_GUARD.allow(requested_max_tokens=1)
            out = emit_metric(name, value, unit=unit)
            return _resp(200, {"emitted": out})

        # --- ROUTE: GET / (health-ish) ------------------------------------
        if method == "GET" and path == "/":
            return _resp(200, {
                "status": "ok",
                "service": "lab6-cost-control-observability",
                "routes": ["GET /estimate?requests_per_day=N", "POST /metric"],
            })

        # --- Unknown route -> 404 -----------------------------------------
        return _resp(404, {"error": f"no route for {method} {path}"})

    except CostGuardError as e:
        # CostGuard ne block kiya => 429 Too Many Requests (cost circuit-breaker).
        return _resp(429, {"error": "cost_guard_blocked", "detail": str(e)})
    except Exception as e:
        # Kuch bhi unexpected => 500, par crash NAHI (Lambda graceful error).
        return _resp(500, {"error": "internal", "detail": str(e)})


# ===========================================================================
# #########################  SELF-DEMO (default)  ##########################
# ===========================================================================
# `uv run <file>` (no args) yahan aata. NO AWS, NO key needed. Exit 0.
# ---------------------------------------------------------------------------
def run_self_demo():
    print("\n" + "#" * 72)
    print("#  LAB 6 SELF-DEMO — Serverless Cost Control + Observability")
    print("#  (NO AWS, NO key needed — sab kuch local, $0)")
    print("#" * 72 + "\n")

    # --- DEMO 1: ESTIMATOR for a few traffic levels -----------------------
    print("=" * 72)
    print("DEMO 1 — estimate_monthly_cost() : 3 traffic levels (money kahan jaata)")
    print("=" * 72)
    # Low traffic: aksar free-tier ke andar => bill ~$0 (sirf Bedrock tokens lagte).
    # High traffic: free-tier cross => Lambda/CW/Bedrock paid zone me. Notice Bedrock
    # line har level par grow karti (kyunki uska koi free-tier nahi).
    for rpd in (100, 5_000, 100_000):
        estimate_monthly_cost(rpd)
        print()

    # --- DEMO 2: emit_metric() — EMF-style metrics ------------------------
    print("=" * 72)
    print("DEMO 2 — emit_metric() : CloudWatch EMF-style JSON (metric -> alarm chain)")
    print("=" * 72)
    print("Yeh JSON lines Lambda logs me jaati; CloudWatch inse metric banata,")
    print("jis par tum ALARM laga ke runaway-cost detect karte ho.\n")
    emit_metric("Invocations", 1, unit="Count", dimensions={"route": "/estimate"})
    emit_metric("BedrockOutputTokens", 134, unit="Count", dimensions={"model": "nova-lite"})
    emit_metric("InvocationLatencyMs", 1000, unit="Milliseconds")
    # Real-AWS path bhi dikhao — boto3/creds nahi hai => clean fallback message.
    print("\n  use_aws=True (boto3/creds nahi => graceful fallback):")
    emit_metric("EstimatedMonthlyUSD", 7.42, unit="None", use_aws=True)
    print()

    # --- DEMO 3: CostGuard — allow vs BLOCK -------------------------------
    print("=" * 72)
    print("DEMO 3 — CostGuard : per-call token cap + per-day request cap enforce")
    print("=" * 72)
    print("AWS hard spend cap NAHI deta => yeh app-level brake hi bachata hai.\n")
    # Chhote caps taaki demo me block dikh sake.
    guard = CostGuard(max_requests_per_day=3, max_tokens_per_call=256)

    # (a) Normal allowed calls (under both caps).
    print("  -> 3 normal calls (max_tokens=128, daily cap=3):")
    for i in range(3):
        guard.allow(requested_max_tokens=128)
        print(f"     call {i + 1} ALLOWED (used_today={guard._used_today})")

    # (b) 4th call: daily request cap hit -> BLOCK.
    print("\n  -> 4th call (daily cap=3 already hit) => expect BLOCK:")
    try:
        guard.allow(requested_max_tokens=128)
        print("     [BUG] block hona chahiye tha!")  # yahan nahi aana chahiye
    except CostGuardError as e:
        print(f"     BLOCKED as expected -> {e}")

    # (c) Token-cap block: fresh guard, ek hi over-limit call.
    print("\n  -> over-limit max_tokens=5000 (cap=256) => expect BLOCK:")
    guard2 = CostGuard(max_requests_per_day=1000, max_tokens_per_call=256)
    try:
        guard2.allow(requested_max_tokens=5000)
        print("     [BUG] block hona chahiye tha!")
    except CostGuardError as e:
        print(f"     BLOCKED as expected -> {e}")
    print()

    # --- DEMO 4: deployable handler() via mock API-Gateway-proxy events ----
    print("=" * 72)
    print("DEMO 4 — handler() : wahi function jo Lambda par deploy hota")
    print("=" * 72)
    print("Hand-built mock API-Gateway-proxy events se invoke kar rahe (NO network):\n")

    # GET / (health)
    ev_health = {"httpMethod": "GET", "path": "/"}
    print("  GET /")
    print("    ->", handler(ev_health, None)["body"])

    # GET /estimate?requests_per_day=5000
    ev_est = {"httpMethod": "GET", "path": "/estimate",
              "queryStringParameters": {"requests_per_day": "5000"}}
    print("\n  GET /estimate?requests_per_day=5000")
    resp = handler(ev_est, None)
    body = json.loads(resp["body"])
    print(f"    -> statusCode={resp['statusCode']}  "
          f"total_monthly_usd=${body['total_monthly_usd']}")

    # POST /metric
    ev_metric = {"httpMethod": "POST", "path": "/metric",
                 "body": json.dumps({"name": "SignupCount", "value": 7, "unit": "Count"})}
    print("\n  POST /metric  {name:SignupCount, value:7}")
    resp = handler(ev_metric, None)
    print(f"    -> statusCode={resp['statusCode']}  body={resp['body']}")
    print()

    print("#" * 72)
    print("#  LAB 6 complete. Yaad rakho:")
    print("#   - Serverless money: Lambda(req+GB-s) + API GW + S3 + CloudWatch + BEDROCK(tokens)")
    print("#   - Bedrock ka koi free-tier nahi => aksar sabse bada bill line")
    print("#   - emit_metric -> CloudWatch metric -> ALARM -> SNS/Budget alert")
    print("#   - AWS hard spend cap NAHI => CostGuard (request cap + max_tokens cap) = brake")
    print("#" * 72 + "\n")

    # Hamesha clean exit 0.
    raise SystemExit(0)


if __name__ == "__main__":
    # Sirf default self-demo (no args). Koi --serve nahi (yeh tool hai, server nahi).
    run_self_demo()
