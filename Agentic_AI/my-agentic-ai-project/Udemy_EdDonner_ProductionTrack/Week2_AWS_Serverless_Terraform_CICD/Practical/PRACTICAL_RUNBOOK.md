# PRACTICAL_RUNBOOK.md — Week 2 Hands-On Guide (Hinglish)

Ye runbook **AI Engineer Production Track** (Ed Donner) ke **Week 2** ka practical/deploy guide hai — **AWS Serverless** (Lambda + S3 + API Gateway + CloudFront + Bedrock) + **Terraform (IaC)** + **CI/CD (GitHub Actions)**. Theory notes (L34–L63 ke topics) tumne padh liye honge; ab actual labs chalana, locally todna, aur **AWS par serverless deploy** karna hai — "Digital Twin Mk2" ko ek real serverless backend ke roop me.

Tum experienced Python backend dev ho, to FastAPI/HTTP/Python basics skip — yahan asli focus **serverless architecture + deployment** hai: stateless Lambda handler (`def handler(event, context)`), API Gateway proxy contract, S3 external memory, Bedrock provider abstraction, Terraform se poora infra declarative banana, aur ek `git push` se auto-deploy karna.

> **Sabse important baat (do baar padho):** labs ko **locally chalana 100% FREE hai** — `uv run ...`, sab `$0`. Har lab boto3 ko **lazy + try/except** se import karta hai, AWS creds na ho to **local filesystem fallback** par chala jaata hai, aur LLM ke liye **Groq free-tier** use karta hai (key na ho to live call skip, sirf shape dikha ke exit 0). **Koi AWS, koi boto3, koi key zaroori nahi** local ke liye. Par jab tum **AWS par deploy** karoge (Lambda + S3 + API Gateway + CloudFront + Bedrock), to wahan **paisa lag sakta hai**. Niche **COST WARNING + TEARDOWN** section dhyaan se padho.

---

## ⚠️ COST WARNING + TEARDOWN (sabse pehle padho)

Ye ek **serverless deployment course** hai. Local sab free hai, par AWS ek alag duniya hai. Sabse khatarnak baat: **AWS par koi HARD SPEND CAP nahi hota** — Budgets sirf *alert* karta hai, paisa **rokta nahi**. Ek bug/loop/forgotten-resource bill ko blow kar sakta hai. Isliye **Budget alert SABSE PEHLE set karo**, fir deploy.

| AWS service | Cost reality | Rule |
|---|---|---|
| **Local** (`uv run ...`) | **$0** — boto3 lazy + local fallback + Groq free-tier. | Jitna chaaho chalao, todo. |
| **Lambda** | Free tier **1M requests/month + 400k GB-seconds/month**. Uske baad: $0.20 per 1M req + ~$0.0000167 per GB-second. Demo twin = practically $0. | Idle me $0 (per-invoke billing). Bada lever = `memory_size` × `duration` (GB-seconds). |
| **S3** (memory bucket) | Storage ~$0.023/GB-month (conversation JSONs KB me => **pennies**); PUT ~$0.005/1k, GET ~$0.0004/1k. Versioning ON => purane versions bhi store hote (thoda extra). | Idle par effectively $0. Teardown me **bucket empty karna padta** (versioned). |
| **API Gateway** (HTTP API) | ~$1.00 per 1M requests (free tier 1M/mo first 12 months). | Per-request, idle $0. |
| **CloudFront** | Free-tier 1 TB/month out; uske baad bandwidth charge. | Static frontend serve karta. Idle $0. |
| **CloudWatch** | Logs ingest ~$0.50/GB + custom metrics ~$0.30/metric/month. **LOG RETENTION = chhupa hua cost** — logs hamesha rakhna = paisa. | dev me `log_retention_days=7`, prod me 90 (tfvars). Teardown me orphaned log groups manually delete karo. |
| **Bedrock** | **Per-TOKEN** (input sasta, output mehenga). Nova Micro ek conversation "radar par bhi nahi", Nova Pro ~3/10 cent/conversation. **Yahi sabse aasaani se add-up hota hai** (loop/abuse par). | `max_tokens` cap + sasta model tier (Nova Micro dev) + CostGuard (lab6). Koi API key nahi — IAM role authorize karta, bill AWS account par. |

> **AWS ka sabse bada gotcha:** koi hard cap nahi. Lambda/S3/API-GW idle par ~$0 dete hain (per-use billing — yahi serverless ka faayda hai vs Week-1 ka always-on App Runner), par **CloudWatch log groups + versioned S3 bucket + Bedrock token spend chupke se add up hote hain**. Isliye kaam khatam = **TURANT TEARDOWN**.

### Step 0 — AWS Budget alert SET karo (L63) — deploy se PEHLE

```bash
# Console: Billing & Cost Management -> Budgets -> Create budget
#   - "Zero spend budget" template (alert jaise hi $0.01 cross ho)
#   - + ek monthly cost budget e.g. $5, threshold 80% par email alert
# Apne email par alert aayega — yahi tumhara safety net hai (HARD CAP nahi, sirf alert).
```

### Step 0.5 — TEARDOWN (kaam khatam hote hi chalao)

Terraform ne jo banaya, Terraform hi **exactly wahi** clean karta hai (state se jaanta hai) — `destroy` sabse safe teardown hai. Phir bhi kuch cheezein (versioned bucket ke purane versions, kabhi-kabhi log group) manually confirm/clean karni padti hain.

```bash
# ---- 1) Terraform destroy (PRIMARY teardown — state se exact resources clean) ----
cd Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/terraform
terraform destroy -var-file=dev.tfvars
# prod alag se deploy kiya tha to:
terraform destroy -var-file=prod.tfvars

# ---- 2) Leftover CloudWatch log group (agar destroy ne na uthaya / pre-existing) ----
# Lambda agar terraform ke bahar bhi ek baar invoke hua to AWS khud log group bana
# deta hai; main.tf ka explicit log group destroy ho jaata, par confirm zaroor karo:
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/twin-" --region us-east-1
aws logs delete-log-group --log-group-name "/aws/lambda/twin-dev-api" --region us-east-1

# ---- 3) S3 memory bucket (VERSIONING ON hai -> pehle EMPTY, fir DELETE) ----
# Versioned bucket seedhe delete nahi hota; terraform destroy aksar handle kar
# leta, par agar "BucketNotEmpty" aaye to manually:
aws s3 rm   s3://twin-dev-memory-<ACCOUNT_ID> --recursive
aws s3api delete-bucket --bucket twin-dev-memory-<ACCOUNT_ID> --region us-east-1
# (Versioned bucket ke chhupe hue versions: Console -> S3 -> bucket -> "Show versions"
#  -> sab select -> delete, ya: aws s3api delete-objects loop. "Empty" button aasaan.)

# ---- 4) CloudFront distribution (agar frontend deploy kiya) ----
# Pehle "Disable" karna padta hai, fir delete (propagate hone me kuch minute lagte).

# ---- 5) Bedrock: koi resource delete nahi (managed) — bas per-token spend ruk jaata
#         jaise hi Lambda invoke karna band. Model access revoke karna optional.

# ---- 6) FINAL: Billing console me confirm ----
# Console -> Billing & Cost Management -> Bills -> Lambda/S3/API-GW/CloudWatch/Bedrock
# ka charge ruk gaya. Budget alert email 1-2 din me settle ho jayega.
```

> **Mantra:** *Deploy karo, dekho, screenshot lo, `terraform destroy` karo.* Cloud ko apni padhai ka demo-stage samjho, permanent ghar nahi. **CloudWatch log retention + versioned S3 = silent cost**, isliye destroy ke baad bhi billing me confirm karo.

---

## 1. Prereqs for REAL deploy (local ke liye kuch nahi chahiye)

Local labs ke liye **kuch extra install nahi** — `uv run` kaafi hai (boto3 lazy hai, na ho to fallback). REAL AWS deploy ke liye:

```bash
# 1) boto3 add karo (AWS SDK for Python). Labs lazy import karte hain — present ho
#    to real S3/CloudWatch path chalta, na ho to local fallback. Deploy ke liye chahiye:
uv add boto3

# 2) AWS CLI configure (LEAST-PRIVILEGE IAM user — root account se NEVER deploy):
#    Console -> IAM -> Users -> create 'twin-deployer' -> Lambda + S3 + API Gateway +
#    CloudWatch Logs + IAM (role pass) + Bedrock ki scoped permissions do (broad
#    AdministratorAccess sirf seekhne ke liye, production me scope karo).
aws configure        # Access Key, Secret, default region=us-east-1, output=json
aws sts get-caller-identity   # verify: account_id + user dikhna chahiye

# 3) Terraform install (labs khud terraform RUN nahi karte; deploy tum karoge):
#    macOS:  brew install hashicorp/tap/terraform
#    fir:    terraform version    # >= 1.5 chahiye (main.tf required_version)

# 4) Placeholders jo niche commands me bharne hain:
#    <REGION>     = us-east-1  (tfvars me default already us-east-1)
#    <ACCOUNT_ID> = 12-digit AWS account number (aws sts get-caller-identity se)
```

> **least-privilege note:** Terraform ka `main.tf` Lambda ko **scoped inline IAM policy** deta hai (sirf is env ke memory bucket par S3 get/put/list/delete + CloudWatch Logs write — `*` nahi). Ye Ed ke `AmazonS3FullAccess`+`AmazonBedrockFullAccess` se zyada production-grade hai. Bedrock access alag se console se request karna padta (niche Section 3c).

---

## 2. Lab → Lecture → Concept → Run Command map

Saare commands **`my-agentic-ai-project` root** se chalao (jahan `pyproject.toml` / `uv` setup hai). Har lab ka **default run = self-demo** (free, no AWS, no boto3, no key zaroori, exit 0): hand-built API-Gateway-proxy events se `handler()` ko invoke karta hai aur statusCode/body print karta hai. boto3+creds ho to real path, warna **local fallback**; GROQ_API_KEY ho to **live LLM**, warna graceful degrade.

| Lab file | Lectures | Kya concept sikhata hai | Run command |
|---|---|---|---|
| `lab1_lambda_handler_apigw.py` | L34–L35, L39, L41, L43 (AWS components, Twin Mk2 arch, deploy to Lambda, API Gateway+CORS) | **Lambda programming model + API Gateway proxy** — koi long-running server nahi; har request = ek INVOCATION, function STATELESS. Cold vs warm start (heavy cheez MODULE TOP par ek baar). API-GW proxy contract (`event` dict -> `{statusCode, headers, body=json.dumps(...)}`, body hamesha STRING). Secrets env vars se. `/health`, `POST /chat` (digital twin). | `uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab1_lambda_handler_apigw.py` |
| `lab2_s3_conversational_memory.py` | L38–L40, L42–L45 (conversational memory, local→S3 migration, CloudFront, CORS) | **S3 external memory for stateless Lambda** — Lambda process memory bhrosa nahi (fresh/killed container). Session state BAHAR (S3 object-per-session `sessions/<id>.json`). Pluggable backend: `LocalFileBackend` (offline) ⇄ `S3Backend` (boto3). Client `session_id` hold karta, server stateless => horizontal scaling. boto3/creds/bucket missing => auto local fallback. | `uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab2_s3_conversational_memory.py` |
| `lab3_bedrock_provider_observability.py` | L46–L49 (setup Bedrock, OpenAI→Bedrock migration, deploy to Lambda, CloudWatch metrics) | **Provider abstraction (OpenAI ⇄ Bedrock) + observability** — `call_llm(prompt)` thin interface ke peeche; provider switch = ek-line config (`BEDROCK_MODEL_ID` set? Bedrock : groq fallback). Bedrock `invoke_model` vs OpenAI `chat.completions` shapes side-by-side (Claude vs Nova/Titan body alag). Har call ke around **structured JSON log** (`event,provider,model,latency_ms,tokens,ok`) -> CloudWatch metrics/alarms. | `uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab3_bedrock_provider_observability.py` (ya `--one` sirf provider + ek log line) |
| `lab4_terraform_iac.py` | L50–L55 (IaC+Terraform, versions/variables/main.tf, outputs+init, multi-env, destroy) | **Infrastructure as Code (Terraform) — THE deploy engine** — declarative IaC vs ClickOps; state file (`.tfstate`, git-ignored); plan-before-apply; multi-env via tfvars (dev/prod); `terraform destroy` teardown. **Ye lab Lambda ZIP build karta** (`build/lambda.zip`), `terraform/*.tf` ko parse+summarize karta, aur exact init/plan/apply/destroy commands print karta (terraform RUN nahi karta). Yahi `handler` Terraform deploy karta (`var.lambda_handler = "lab4_terraform_iac.handler"`). | `uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab4_terraform_iac.py` (ya `--build` sirf zip) |
| `lab5_cicd_pipeline.py` | L56–L62 (GitHub Actions intro→git→remote backend→OIDC→deploy.yaml→live→loop) | **CI/CD pipeline (GitHub Actions) — LOCAL dry-run** — har push -> TEST -> BUILD -> DEPLOY gates (`needs:` chain; test fail => build nahi). OIDC (short-lived token, no stored key) vs long-lived keys. Lab **dry-run**: `aws`/`terraform` commands PRINT karta (execute nahi), par zip build + `py_compile` REAL/free. Sibling `cicd/deploy.yml` exactly yahi pipeline hai. | `uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab5_cicd_pipeline.py` (ya `--build-only` / `--invoke`) |
| `lab6_cost_control_observability.py` | L49, L63 (CloudWatch metrics; Day 5 resource management & cost control) | **Cost control + observability (FinOps in code)** — serverless paisa kahan jaata (Lambda GB-sec, S3, API-GW, CloudWatch, Bedrock per-token) — itemized budget report + free-tier deductions. `emit_metric()` EMF-ish JSON -> CloudWatch metric -> alarm. **CostGuard** = THE lesson: AWS me koi hard cap nahi, isliye DEFENCE app ke andar — per-day request cap + per-call `max_tokens` cap, limit cross => call BLOCK (circuit breaker). Pure-Python, no AWS needed. | `uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab6_cost_control_observability.py` |

> Note: lecture numbers concept-wise mapping hain. Exact lecture ke liye apne Week2 theory notes ka topic match kar lo.

### Quick start (sab FREE, no AWS, no key, self-demo, exit 0)

```bash
# my-agentic-ai-project root se:
uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab1_lambda_handler_apigw.py
uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab2_s3_conversational_memory.py
uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab3_bedrock_provider_observability.py
uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab4_terraform_iac.py
uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab5_cicd_pipeline.py
uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab6_cost_control_observability.py
```

> Note: Week 2 labs me Week-1 jaisa `--serve` uvicorn flag **nahi** hai — ye labs **Lambda handlers** hain, long-running servers nahi. Default run hi handler ko mock API-Gateway events se invoke karta hai (yahi serverless mental model). Asli HTTP test deploy ke baad API Gateway URL par `curl` se hota hai (Section 3a).

---

## 3. Deploy recipes (EXACT commands)

Sab kuch `terraform/` + `cicd/` me ready hai:
- `terraform/main.tf` — poora stack: IAM role + scoped inline policy, S3 memory bucket (public-access blocked + versioning), CloudWatch log group (retention!), Lambda function (zip se), API Gateway HTTP API v2 (`$default` catch-all route, AWS_PROXY, payload v2.0, CORS), `aws_lambda_permission`.
- `terraform/variables.tf` — knobs: `region`, `project_name=twin`, `environment` (validated dev/test/prod), `lambda_zip_path=../build/lambda.zip`, `lambda_handler=lab4_terraform_iac.handler`, `lambda_runtime=python3.12`, timeout/memory, `bedrock_model_id`, `log_retention_days`, `cors_allow_origins`.
- `terraform/outputs.tf` — `api_endpoint`, `memory_bucket_name`, `lambda_function_name`, `log_group_name` (downstream automation ka contract).
- `terraform/dev.tfvars` — dev values (Nova Micro, timeout 30, mem 256, retention 7, CORS `*`).
- `terraform/prod.tfvars` — prod values (Nova Pro, timeout 60, mem 512, retention 90, CORS locked to `https://twin.example.com` — apni asli domain se replace karo).
- `cicd/deploy.yml` — GitHub Actions workflow (test → package → deploy, OIDC).

### (a) Terraform serverless stack deploy — dev (PAID — TEARDOWN zaroori!)

```bash
# --- 0) Budget alert set kar liya? (Section Step 0) Bedrock access enable? (3c) ---

# --- 1) Lambda ZIP build karo PEHLE (terraform isi zip ko deploy karta) ---
# lab4 ka packager handler file ko build/lambda.zip me pack karta (offline, free):
uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab4_terraform_iac.py --build
# => Practical/build/lambda.zip banti hai (andar lab4_terraform_iac.py, jo
#    var.lambda_handler="lab4_terraform_iac.handler" se match karta).

# --- 2) terraform folder me jao ---
cd Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/terraform

# --- 3) init (ek baar) -> plan (dry-run diff) -> apply ---
terraform init
terraform plan  -var-file=dev.tfvars      # APPLY se PEHLE diff dekho (L50 non-negotiable)
terraform apply -var-file=dev.tfvars      # interactive 'yes' maangega -> haan

# --- 4) API endpoint output nikaalo + curl test ---
terraform output -raw api_endpoint        # e.g. https://abc123.execute-api.us-east-1.amazonaws.com
API=$(terraform output -raw api_endpoint)
curl "$API/health"                                          # {"status":"ok"} type
curl -X POST "$API/chat" -H "Content-Type: application/json" \
     -d '{"message":"hello twin","session_id":"demo-1"}'    # digital twin reply
# Memory verify: doosri call wahi session_id se -> history yaad rahegi (S3 me persist):
aws s3 ls s3://$(terraform output -raw memory_bucket_name)/sessions/

# --- 5) Logs dekho (CloudWatch) ---
aws logs tail "$(terraform output -raw log_group_name)" --follow --region us-east-1
```

**Multi-env (dev vs prod):** same `main.tf`, alag tfvars. prod ke liye:
```bash
terraform plan    -var-file=prod.tfvars
terraform apply   -var-file=prod.tfvars     # Nova Pro, mem 512, retention 90, CORS locked
# (Best practice L54: prod ke liye ALAG IAM user/account use karo — permission isolation.)
```
> Resource naming `${project_name}-${environment}` se hota (`twin-dev-api`, `twin-prod-api`), bucket `twin-dev-memory-<ACCOUNT_ID>` (globally-unique account suffix) — isliye dev+prod ek account me bina collision ke coexist karte hain. **Dono deploy kiye to dono `terraform destroy` karna** (`-var-file=dev.tfvars` aur `-var-file=prod.tfvars`).

### (b) CI/CD pipeline — `git push` se auto-deploy

`cicd/deploy.yml` ek teaching/reference copy hai; GitHub Actions ise tabhi chalata jab **repo root ke `.github/workflows/`** me ho.

```bash
# --- 1) Workflow ko sahi jagah copy karo ---
mkdir -p .github/workflows
cp Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/cicd/deploy.yml \
   .github/workflows/deploy.yml

# --- 2) Repo secrets set karo (OIDC — recommended, no stored keys) ---
# GitHub -> repo -> Settings -> Secrets and variables -> Actions -> New secret:
#   AWS_ROLE_ARN          = OIDC IAM role ka ARN (L59 me Terraform se banaya — trust
#                           policy repo:owner/name:* par scoped)
#   AWS_DEFAULT_REGION    = us-east-1
# (Fallback long-lived keys: AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY — AVOID, leak/rotate
#  headache. deploy.yml me commented fallback example hai.)

# --- 3) Remote Terraform backend ek baar bana lo (pipeline isse use karta) ---
# deploy.yml init step expect karta: S3 state bucket 'twin-terraform-state' +
# DynamoDB lock table 'twin-terraform-locks' (L58). Ye ek baar banao (console/CLI).

# --- 4) Push to main -> pipeline AUTO chalega ---
git add .github/workflows/deploy.yml
git commit -m "ci: add serverless deploy workflow"
git push origin main
# GitHub -> Actions tab -> "Deploy Digital Twin" run dekho.
```

**Pipeline ke 3 jobs (gate-chain `test -> package -> deploy`):**
1. **test** — checkout, Python 3.12 + uv setup, `uv sync` (lockfile = reproducible), `py_compile` gate (syntax/import crash pakda), `pytest` (demo me `|| true` soft-pass; production me `|| true` HATA do).
2. **package** (`needs: test`) — `uv run python Practical/lab5_cicd_pipeline.py --build-only` se `build/lambda.zip` banata, `actions/upload-artifact` se share (jobs alag VMs par => disk share nahi, artifact se pass).
3. **deploy** (`needs: package`) — artifact download, **OIDC se AWS creds** (`role-to-assume`, `id-token: write` permission CRITICAL), Terraform install, `terraform init` (remote S3 backend + DynamoDB lock), `workspace select/new $DEPLOY_ENV` (L54), `terraform apply -auto-approve -var-file=$DEPLOY_ENV.tfvars`, `aws lambda update-function-code` se naya zip push (`--publish`), aur `api_endpoint`/`memory_bucket_name` ko GitHub Job Summary me likhta.

> **Triggers:** `push: main` => auto-deploy to **dev** (`DEPLOY_ENV` default `dev`). Manual **workflow_dispatch** button => `environment` choice (dev/test/prod) — yahi safety gating (dev auto, test/prod manual). `deploy` job ka `environment:` GitHub Environments use karta (prod par required-reviewers/approval laga sakte ho).

### (c) Bedrock enablement (per-token, deploy se pehle)

Bedrock models **default OFF** hote — pehle access maango:
```text
1) Console -> Amazon Bedrock -> Model access -> "Manage model access"
2) Jo model chahiye select karo: dev = amazon.nova-micro-v1:0 (sasta),
   prod = amazon.nova-pro-v1:0 (behtar) — ya Anthropic Claude (alag body shape).
3) Request submit -> aksar instant/jaldi approve.
4) Region match karo (tfvars region = us-east-1; Bedrock model usi region me enable ho).
5) BEDROCK_MODEL_ID set: Terraform isse Lambda env me wire karta (main.tf -> environment ->
   BEDROCK_MODEL_ID = var.bedrock_model_id). Set ho to lab3 ka call_llm Bedrock use karta,
   warna groq fallback. Koi API key nahi — Lambda ki IAM execution role authorize karti,
   bill AWS account par (per-token).
```
> dev me Nova Micro (token cost "radar par bhi nahi"), prod me Nova Pro — `tfvars` already isi par set hai.

---

## 4. Cost-control box

| Lever | Kya karo | Kyun |
|---|---|---|
| **Lambda free tier** | 1M req/mo + 400k GB-sec free; `lambda_memory_mb` chhota (dev 256) + `lambda_timeout` reasonable | GB-seconds = `memory_GB × duration × requests` — yahi Lambda ka bada charge. Idle par $0 (per-invoke). |
| **Bedrock token caps** | `max_tokens` cap har call par; dev = Nova Micro, prod = Nova Pro; **CostGuard** (lab6) per-day request cap + per-call token cap | Bedrock per-TOKEN bill, output mehenga. AWS me hard cap nahi — app-level circuit breaker hi runaway loop rokta. |
| **CloudWatch log retention** | `log_retention_days` set karo (dev 7, prod 90) — main.tf me explicit log group isiliye declare kiya | Logs "hamesha" rakhna = recurring storage cost + teardown me orphaned log group. Retention = auto-expire. |
| **Budget alerts** | Deploy se PEHLE zero-spend + monthly budget (L63, Section Step 0) | AWS par **HARD CAP NAHI** — alert hi tumhara safety net. |
| **Local-first** | Sab labs default boto3-lazy + local fallback + Groq free-tier; deploy sirf tab jab local pakka chale | LLM/AWS cost $0 jab tak deploy na karo. Cloud par debug = paisa + time waste. |
| **TEARDOWN** | `terraform destroy -var-file=<env>.tfvars` + versioned S3 empty + log group confirm + billing check | Versioned bucket + log groups silent cost. Destroy = state se exact clean. |

> Ed ka pura course estimate: **~$5–$10**, zyaadatar free-tier ke andar (+optional domain ~$15/year). Discipline rakho (Groq local + Nova Micro dev + caps + retention + destroy) to actual spend ~$0–$2.

---

## 5. Common errors & fixes

| Error / symptom | Wajah | Fix |
|---|---|---|
| `[INFO] AWS not configured -> local fallback` / "S3 backend unavailable, using local file" | boto3 missing, ya AWS creds nahi, ya `S3_BUCKET`/`MEMORY_BUCKET` set nahi | **Expected** local par — labs auto-fallback karte hain (`./_s3_memory/` ya `build/memory/`), exit 0. Real S3 chahiye to `uv add boto3` + `aws configure` + bucket env set. |
| `GROQ_API_KEY missing => skipping live call` / deterministic "echo" reply | `.env` me `GROQ_API_KEY` nahi | **Expected** — handler shape dikha ke exit 0 deta. Live twin reply chahiye to `.env` me `GROQ_API_KEY=gsk_...` add karo. |
| Lambda **Task timed out after N seconds** | `lambda_timeout` chhota; LLM call slow (Bedrock cold / bada prompt) | `variables.tf`/tfvars me `lambda_timeout` badhao (dev 30 -> 60). Heavy init module-top par rakho (warm reuse). |
| Lambda **memory / `Runtime exited` / OOM** | `lambda_memory_mb` kam | `lambda_memory_mb` badhao (256 -> 512). Memory zyada => CPU bhi zyada (AWS coupled) => tezz, par mehenga. |
| `AccessDenied` / `is not authorized to perform: s3:PutObject` (ya bedrock/logs) | IAM role/policy scope kam, ya Bedrock model access nahi maanga | main.tf ki scoped inline policy IS env ke bucket+logs tak hi deti — bucket naam match karo. Bedrock: Console -> Model access enable (3c). Deployer user ke paas zaroori permissions confirm karo. |
| API Gateway **502 Bad Gateway** / "Internal server error" | Lambda ne galat shape return kiya — `{statusCode,headers,body}` chahiye, `body` ek **STRING** (`json.dumps(...)`), dict nahi | Handler return shape check karo: `body` hamesha `json.dumps(...)`. AWS_PROXY integration is exact contract par strict hai. CloudWatch logs me asli exception dikhega. |
| API Gateway **403 / "Missing Authentication Token"** ya route 404 | Galat path, ya `aws_lambda_permission` missing, ya route mismatch | main.tf `$default` catch-all route + `aws_lambda_permission.apigw` (API-GW ko invoke ki ijaazat) deta — `terraform apply` ne ye bana diya confirm karo. Sahi `$API/<path>` hit karo. |
| Browser se call par **CORS error** (`No 'Access-Control-Allow-Origin'`) | `cors_allow_origins` me frontend origin nahi | dev `*` hota; prod me `prod.tfvars` ka `cors_allow_origins` apni asli CloudFront/domain par set karo (`https://twin.example.com` placeholder replace karo). |
| `Error acquiring the state lock` / `ConditionalCheckFailedException` | Terraform state DynamoDB lock stuck (pichla apply crash/interrupt) | Wait karo (doosra apply chal raha ho to). Stale lock: `terraform force-unlock <LOCK_ID>` (ID error me deta). Remote backend = `twin-terraform-locks` table. |
| `terraform plan/apply` -> `no such file ../build/lambda.zip` / `filebase64sha256` fail | Zip build nahi ki / galat CWD | Pehle `lab4 --build` chalao (Section 3a step 1). `lambda_zip_path` default `../build/lambda.zip` hai => `terraform/` se relative; isliye `cd terraform` ke baad apply karo. |
| GitHub Actions deploy job -> `Could not assume role` / `Not authorized to perform sts:AssumeRoleWithWebIdentity` | OIDC role ARN galat/missing, ya trust policy repo se match nahi, ya `id-token: write` permission nahi | `AWS_ROLE_ARN` secret sahi ARN; role ki trust policy `repo:<owner>/<repo>:*` allow kare; `permissions: id-token: write` deploy.yml me hai confirm karo (L59). |
| GitHub Actions -> `terraform init` backend error / bucket not found | Remote state bucket/lock table nahi banaya | `twin-terraform-state` S3 bucket + `twin-terraform-locks` DynamoDB table ek baar banao (L58), fir push. |
| `AuthenticationError`/`401` LLM call par | `OPENAI_API_KEY` me galti se Google key (is `.env` ka quirk — Section 6) | Local ke liye **Groq hi rakho** (default `get_client("groq")`). Bedrock prod me. OpenAI chahiye to asli `sk-...` set karo. |
| `command not found: terraform` / `uv` / `aws` | Tool installed nahi | `terraform`: `brew install hashicorp/tap/terraform`; `uv`: https://docs.astral.sh/uv/ ; `aws`: AWS CLI v2 install. |
| Galat folder se run | Relative path resolve nahi hua | `uv run ...` hamesha **`my-agentic-ai-project` root** se. Terraform commands **`Practical/terraform/`** se. Zip build root se (`lab4 --build`). |

---

## 6. `.env` key quirk (zaroor padho)

Is user ke root `.env` me:

```bash
GROQ_API_KEY=gsk_...     # ✅ VALID, free-tier  -> local runs ke liye yahi use karo (preferred)
GOOGLE_API_KEY=...       # ✅ VALID (Gemini ke liye, gemini-2.5-flash)
OPENAI_API_KEY=...       # ⚠️ is .env me yeh actually ek GOOGLE key hold karta hai —
                         #    asli OpenAI key NAHI. Isliye get_client("openai") fail karega.
```

> **Practical advice:** local runs ke liye **hamesha Groq** (`get_client("groq")`, har lab ka default) — free, fast, aur key valid hai. Gemini try karna ho to `get_client("gemini")` + `GOOGLE_API_KEY`. **OpenAI tab tak avoid karo** jab tak asli `sk-...` set na karo — warna 401. Cloud me ye sab irrelevant: Bedrock me **koi API key nahi** — Lambda ki IAM execution role authorize karti hai.

---

## 7. Order to do them in (aur kyun)

1. **lab1** — Lambda programming model + API Gateway proxy contract (stateless handler ka foundation). (L34–L43)
2. **lab2** — S3 external memory: stateless Lambda ko conversational memory do (local→S3 migration, pluggable backend). (L38–L45)
3. **lab3** — Bedrock provider abstraction + CloudWatch-style structured observability (OpenAI⇄Bedrock ek-line swap). (L46–L49)
4. **lab4** — **Terraform IaC** — poora infra declarative banao + zip build + multi-env + destroy (yahi deploy engine hai). (L50–L55)
5. **lab5** — **CI/CD** — `git push` -> test→build→deploy pipeline (OIDC, gates), local dry-run. (L56–L62)
6. **lab6** — **Cost control + observability** — FinOps in code: budget report, EMF metrics, CostGuard circuit breaker. (L49, L63)

> Logic: lab1–lab3 serverless app ke 3 building blocks (compute + state + provider/observability) banate hain; lab4 unhe Terraform se reproducibly deploy karta; lab5 us deploy ko `git push` par automate karta; lab6 poore stack ko cost-safe banata. Yahi Week-1 (Vercel/App Runner ClickOps) se Week-2 (IaC + CI/CD serverless) ka jump hai.

---

## 8. Week 2 done = milestone

**Week 2 khatam matlab tum ek production serverless AI app deploy kar sakte ho** — jo:
- ek **stateless Lambda** `handler(event, context)` ho jo API Gateway proxy contract sahi follow kare (`{statusCode, headers, body=json.dumps(...)}`),
- conversation memory **S3** me external rakhe (horizontal scaling free),
- LLM provider ko **Bedrock ⇄ groq** ek-line config se swap kare + structured logs se observable ho,
- poora infra **Terraform** se declarative ho (plan-before-apply, multi-env dev/prod, `terraform destroy` teardown),
- ek **`git push` se CI/CD** (test→build→deploy, OIDC, gates) se auto-deploy ho,
- aur — sabse important — **tumhe pata ho serverless me paisa kahan jaata hai (Lambda GB-sec / S3 / API-GW / CloudWatch retention / Bedrock token), AWS me HARD CAP nahi hota, budget alert + CostGuard pehli defence hai, aur kaam ke baad `terraform destroy` + manual cleanup (versioned S3, log groups) + billing confirm kaise karna hai.**

> **Compare against the official repo:** Ed ke exact versions (Mangum/FastAPI-on-Lambda, `bedrock.converse`, deploy.sh/destroy.sh, full IAM full-access policies) ke saath apne labs milao — jahan farak ho wahan samjho kyun (concept same, implementation tumne self-contained + local-fallback + scoped-policy banaya).

---

### TL;DR

```bash
# LOCAL (free): root se koi bhi lab —
uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab1_lambda_handler_apigw.py

# DEPLOY (paid): budget alert -> zip -> terraform —
uv run Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/lab4_terraform_iac.py --build
cd Udemy_EdDonner_ProductionTrack/Week2_AWS_Serverless_Terraform_CICD/Practical/terraform
terraform init && terraform plan -var-file=dev.tfvars && terraform apply -var-file=dev.tfvars

# TEARDOWN (zaroori): kaam khatam hote hi —
terraform destroy -var-file=dev.tfvars   # + versioned S3 empty + log group + billing confirm
```

Locally sab free me todo. Cloud par tab jao jab ready ho — aur **kaam khatam hote hi `terraform destroy`** (Section 0.5). Happy shipping. 🚀
