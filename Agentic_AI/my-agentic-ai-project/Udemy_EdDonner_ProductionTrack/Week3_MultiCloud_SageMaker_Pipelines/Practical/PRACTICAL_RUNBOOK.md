# PRACTICAL_RUNBOOK.md — Week 3 Hands-On Guide (Hinglish)

Ye runbook **AI Engineer Production Track** (Ed Donner) ke **Week 3** ka practical/deploy guide hai — **Multi-cloud** (Azure Container Apps + GCP Cloud Run) + **SageMaker vs Bedrock embeddings** + **Vector / RAG data pipelines** (chunk → embed → store → retrieve → generate) + **EventBridge scheduled agents**. Theory notes (L64–L88 ke topics) tumne padh liye honge; ab actual labs chalana, locally todna, aur — jab ready ho — **3 alag clouds** (Azure, GCP, AWS/SageMaker) par deploy karna hai. Ye Week-2 (single-cloud AWS serverless) se bada jump hai: ab **"build once, run anywhere"** (ek container, kai cloud) + **apna embedding model host karna** (SageMaker) + **RAG ka pura data plumbing**.

Tum experienced Python backend dev ho, to FastAPI/HTTP/Docker basics skip — yahan asli focus hai: **container portability across clouds** (ek image Azure + GCP + AWS, zero code change), **provider abstraction** (`get_embeddings()` ke peeche SageMaker / Bedrock / local-hash), **vector ingest pipeline** (chunk+overlap → embed → pluggable store → cosine retrieve), **RAG loop** (retrieve→augment→generate with citations), aur **managed cron** (EventBridge push-scheduling vs always-on box).

> **Sabse important baat (do baar padho):** labs ko **locally chalana 100% FREE hai** — `uv run ...`, sab `$0`. Har lab apne heavy deps ko **lazy + try/except** se import karta hai aur graceful degrade karta hai:
> - **boto3** (AWS SDK) lazy hai → na ho ya creds na ho to **local fallback** (LocalHashEmbedder / LocalJSONStore / local mock run).
> - **semgrep** binary/module lazy hai (lab1) → na ho to built-in **regex/AST mini-scanner** par girta hai (no network, no crash).
> - **embeddings** ke liye `sentence-transformers`/SageMaker/Bedrock na ho to **numpy-hash embedder** (deterministic, offline, zero download).
> - **LLM** ke liye **Groq free-tier** (`get_client("groq")`) — key na ho to live call SKIP karke templated/grounded output deta hai, exit 0.
>
> **Koi cloud, koi boto3, koi semgrep, koi key zaroori nahi** local ke liye. Par jab tum **Azure / GCP / AWS-SageMaker par deploy** karoge, to wahan **paisa lag sakta hai** — aur SageMaker endpoint ka ek **chhupa hua per-hour gotcha** hai (niche). **COST WARNING + TEARDOWN** section dhyaan se padho.

---

## ⚠️ COST WARNING + TEARDOWN (sabse pehle padho — Week 3 me ye sabse zaroori section hai)

Week 3 me tum **3 alag cloud accounts** chhoo rahe ho (Azure, GCP, AWS). Teeno ka ek hi sach: **kisi par bhi HARD SPEND CAP nahi hota** — budget sirf *alert* karta hai, paisa **rokta nahi**. Isliye **teeno clouds par budget alert SABSE PEHLE set karo**, fir deploy.

Aur Week-3 ka **#1 paisa-khaane wala gotcha**: 👇

> ### 🔴 SAGEMAKER ENDPOINT = PER-HOUR BILLING (chahe koi use kare ya na kare)
> Ek **provisioned SageMaker endpoint chalu chhodna sabse aasaani se bhula jaane wala + sabse mehnga** Week-3 mistake hai. Lambda/Cloud Run/ACA **idle par scale-to-zero** karte hain (per-request) — par **SageMaker provisioned endpoint GHANTE ke hisaab se bill karta hai, chahe ek bhi request na aaye, chahe tum so rahe ho.** ml.t2.medium ~$0.06/hr lagta chhota, par 24×30 = ~$43/month sirf ek idle endpoint par. **Endpoint deploy kiya = us din DELETE karo.** (Serverless SageMaker endpoint pay-per-use hota — wo idle par sasta — par phir bhi cleanup karo.)
>
> **Pehla kaam jab bhi SageMaker chhoo: `aws sagemaker list-endpoints` se check karo koi chalu to nahi. Aakhri kaam: `aws sagemaker delete-endpoint`.**

| Service / resource | Cost reality | Rule |
|---|---|---|
| **Local** (`uv run ...`) | **$0** — boto3/semgrep lazy + numpy-hash embed + LocalJSONStore + Groq free-tier. | Jitna chaaho chalao, todo. |
| **Azure Container Apps** (`azure_container_app.tf`) | Consumption plan: **idle par scale-to-zero (min_replicas=0 → $0)**. Active par vCPU-second + GiB-second. Demo app daily kuch cents (L69 me Ed ko ~$0.17/day laga jab galti se chalu chhoda). **ACR (Azure Container Registry) Basic ~$0.167/day (~$5/mo) — ye scale-to-zero NAHI hota, registry hamesha bill karta.** Free credits (~$200/30din) me aata. | `min_replicas=0` already set. ACR alag se delete karo (registry idle bhi charge). |
| **GCP Cloud Run** (`gcp_cloud_run.tf`) | Bhi **scale-to-zero (min_instance_count=0 → idle $0)**. Per-request + vCPU/memory-second. Bada free tier (~2M req/mo). Artifact Registry me image storage chhota par non-zero. Demo effectively free. | `min_instance_count=0` already set. Artifact Registry repo cleanup karo. |
| **AWS SageMaker** (embedding endpoint, L77) | 🔴 **Provisioned endpoint = PER-HOUR, idle bhi charge** (sabse bada Week-3 gotcha). Serverless endpoint = pay-per-use (idle ~$0). | **Deploy → use → `aws sagemaker delete-endpoint` USI DIN.** Roz `list-endpoints` check. |
| **AWS Bedrock** (Titan embed / Nova, L76/L84) | **Per-TOKEN** (managed, koi endpoint nahi, idle $0). Embeddings micro-charge per input token. | Koi API key nahi — IAM role authorize karta. Loop/abuse par add-up. |
| **S3 vector storage** (S3 Vectors / bucket, L80) | Storage ~$0.023/GB-month (vectors+text KB-MB me → pennies); PUT/GET micro-charge. **OpenSearch ke ~90% sasta** (L79: OpenSearch ne Ed ka ~$50 kha liya — isliye S3 Vectors). Versioning ON (L81 SSE) → purane versions extra. | Idle ~$0. Teardown me bucket **empty fir delete** (versioned). |
| **Lambda** (ingestion handler, L80/L81) | Free tier 1M req + 400k GB-sec/mo. Per-invoke billing → idle $0. | Ingest trigger; idle $0. |
| **EventBridge** (`eventbridge_schedule.tf`, L87) | Rule/schedule lagbhag free (~14M custom events/mo free tier). **Asli kharcha har TICK par downstream run** (Lambda + Bedrock + SageMaker embed + S3). `rate(2 hours)` = din me 12 runs. | `scheduler_enabled=false` (SAFE default) ya cadence ghatao (`rate(2 hours)`→`rate(20 hours)`). |
| **API Gateway** (secure ingest, L81) | ~$1/1M req (free tier 1M/mo first 12mo). Per-request, idle $0. | Ingest endpoint; idle $0. |

> **Teeno clouds ka mantra:** *Deploy karo, dekho, screenshot lo, `terraform destroy` karo.* Cloud ko demo-stage samjho, ghar nahi. **SageMaker endpoint per-hour + ACR registry + versioned S3 = silent cost.** Destroy ke baad bhi **teeno** billing consoles me confirm karo.

### Step 0 — Budget alerts SET karo (teeno clouds par) — deploy se PEHLE

```text
AWS    : Console -> Billing & Cost Management -> Budgets -> "Zero spend budget" template
         + ek monthly cost budget (e.g. $10, 80% par email). (HARD CAP nahi, sirf alert.)
Azure  : Portal -> Cost Management -> Budgets -> Create (scope = subscription/RG;
         e.g. $10/mo, alert at 80%). (L67 me Ed budget alert pehle set karta.)
GCP    : Console -> Billing -> Budgets & alerts -> Create budget (e.g. $10/mo, 90% alert).
```

### Step 0.5 — TEARDOWN (kaam khatam hote hi chalao — har stack apna)

Terraform ne jo banaya, Terraform hi **exactly wahi** clean karta hai (state se jaanta hai) → `destroy` sabse safe. **Har deploy alag stack hai → har ek ko alag destroy karo.** SageMaker endpoint Terraform ke bahar bhi ban sakta tha (CLI/console se), isliye uske liye explicit `delete-endpoint` bhi.

```bash
# ===== A) AZURE Container Apps stack (deploy/azure_container_app.tf) =====
cd Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/deploy
terraform workspace select azure
terraform destroy -var "image=<acr-login-server>/multicloud-agent:latest" -var "groq_api_key=$GROQ_API_KEY"
# RG destroy hote hi RG-ke-andar sab (container app, env, log workspace) chala jaata.
# Phir bhi confirm (RG khaali na reh jaaye):
az group delete --name multicloud-agent-rg --yes --no-wait
# ACR registry agar alag banaya tha (scale-to-zero NAHI hota — idle bhi $$$):
az acr delete --name <ACR_NAME> --resource-group multicloud-agent-rg --yes

# ===== B) GCP Cloud Run stack (deploy/gcp_cloud_run.tf) =====
terraform workspace select gcp
terraform destroy -var "image=<region>-docker.pkg.dev/<proj>/<repo>/multicloud-agent:latest" -var "groq_api_key=$GROQ_API_KEY"
# Confirm service gaya:
gcloud run services delete multicloud-agent --region us-central1 --quiet
# Artifact Registry repo (image storage) bhi delete (idle storage charge):
gcloud artifacts repositories delete <repo> --location <region> --quiet

# ===== C) AWS SAGEMAKER endpoint (🔴 PER-HOUR — sabse pehle dekho!) =====
aws sagemaker list-endpoints --region us-east-1                 # koi chalu to nahi?
aws sagemaker delete-endpoint        --endpoint-name alex-embedding-endpoint --region us-east-1
aws sagemaker delete-endpoint-config --endpoint-config-name alex-embedding-endpoint --region us-east-1
aws sagemaker delete-model           --model-name alex-embedding-model --region us-east-1
# (Agar Terraform se banaya tha to `terraform destroy` bhi uthaa lega — par list-endpoints
#  se DOBARA confirm karo. Endpoint bill ghante se ho raha tha; ek minute bhi late = paisa.)

# ===== D) S3 vector storage (versioned -> EMPTY fir DELETE) =====
aws s3 rm   s3://alex-vectors-<ACCOUNT_ID> --recursive
aws s3api delete-bucket --bucket alex-vectors-<ACCOUNT_ID> --region us-east-1
# (Versioned bucket: Console -> S3 -> bucket -> "Show versions" -> select all -> delete,
#  ya "Empty" button. BucketNotEmpty aaye to versions bache hain.)

# ===== E) EventBridge rule (deploy/eventbridge_schedule.tf) =====
terraform destroy   # is module ke andar (scheduler_enabled default false => waise hi 0 resource)
# Manual confirm / CLI cleanup (agar rule bana tha):
aws events list-rules --region us-east-1 --name-prefix alex
aws events remove-targets --rule alex-research-schedule --ids alex-research-lambda --region us-east-1
aws events delete-rule    --name alex-research-schedule --region us-east-1

# ===== F) Lambda + leftover CloudWatch log groups =====
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/alex" --region us-east-1
aws logs delete-log-group --log-group-name "/aws/lambda/alex-scheduler" --region us-east-1

# ===== G) FINAL: teeno billing consoles me confirm (AWS / Azure / GCP) =====
# SageMaker endpoint charge ruk gaya? ACR/Artifact Registry storage? Budget alerts settle?
```

> **Bedrock:** koi resource delete nahi (fully managed) — bas per-token spend ruk jaata jab call band. Model access revoke optional.

---

## 1. Prereqs for REAL deploy (local ke liye kuch nahi chahiye)

Local labs ke liye **kuch extra install nahi** — `uv run` kaafi (boto3/semgrep lazy, na ho to fallback). REAL multi-cloud deploy ke liye:

```bash
# --- 1) boto3 (AWS SDK) — SageMaker / S3 Vectors / Lambda / EventBridge ke liye ---
#     Labs lazy import karte; present + creds ho to real AWS path, warna fallback.
uv add boto3

# --- 2) semgrep (lab1 real SAST scan) — optional; na ho to built-in mini-scanner ---
uv add semgrep         # ya: brew install semgrep / pipx install semgrep
semgrep --version      # verify

# --- 3) Terraform (teeno .tf isi se deploy hote; labs khud terraform RUN nahi karte) ---
brew install hashicorp/tap/terraform
terraform version      # >= 1.5

# --- 4) Docker (image build — multi-cloud ka artifact) ---
docker --version       # Docker Desktop chalu ho

# --- 5) AWS CLI (SageMaker / S3 / EventBridge) ---
aws configure          # Access Key, Secret, region=us-east-1, output=json
aws sts get-caller-identity
#   SageMaker + Bedrock MODEL ACCESS alag se request karo (niche Section 3d/3f):
#   - Bedrock: Console -> Bedrock -> Model access -> amazon.titan-embed-text-v2:0 (+Nova)
#   - SageMaker: SageMakerFullAccess + S3 Vectors policy (L75 Alex-Access group)

# --- 6) Azure CLI ---
brew install azure-cli   # macOS
az login                 # browser se login (L67)
az account show          # subscription confirm
#   Resource providers register (L68 — pehli baar):
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights

# --- 7) gcloud CLI (GCP) ---
brew install --cask google-cloud-sdk
gcloud auth login                       # user login (L72)
gcloud auth application-default login   # ADC — Terraform google provider isse uthata (L72)
gcloud config set project <PROJECT_ID>
gcloud auth configure-docker <region>-docker.pkg.dev   # Artifact Registry push ke liye
```

> **Placeholders** jo niche commands me bharne hain: `<ACCOUNT_ID>` (AWS 12-digit), `<ACR_NAME>` / `<acr-login-server>` (Azure registry), `<PROJECT_ID>` / `<repo>` / `<region>` (GCP).

---

## 2. Lab → Lecture → Concept → Run Command map

Saare commands **`my-agentic-ai-project` root** se chalao (jahan `pyproject.toml` / `uv` setup hai). Har lab ka **default run = self-demo** (free, no cloud, no boto3/semgrep/key zaroori, exit 0). Heavy dep ho to real path; warna **graceful fallback** (numpy-hash embed / mini-scanner / local store / Groq).

| Lab file | Lectures | Kya concept sikhata hai | Run command |
|---|---|---|---|
| `lab1_cybersecurity_agent_semgrep_triage.py` | L64–L66 (Multi-cloud + cyber agent intro; Semgrep+MCP; containerize) | **Security agent = SCAN tool + LLM reasoning.** `scan_code()` = MCP-style `semgrep_scan` tool (input=code, output=structured findings); **SAST** = code chalaye bina pattern-match (eval/exec, hardcoded secrets, shell=True, pickle, md5, SQL concat); LLM har finding ko **explain + triage** (CVSS-style severity sort). **semgrep lazy** → na ho to regex/AST mini-scanner; **groq lazy** → na ho to templated explanation. | `uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab1_cybersecurity_agent_semgrep_triage.py` (`--scan-only` LLM skip; `--file path.py` apni file scan) |
| `lab2_multicloud_container_deploy.py` | L66–L73 (Docker; Azure infra; ACA via Terraform; GCP infra+gcloud; Cloud Run; 4-env parity) | **Build-once-run-anywhere.** Ek chhota FastAPI agent (`GET /health` = liveness probe, `POST /chat`) = ek container workload. **BILKUL wahi image** local + Azure (ACA) + GCP (Cloud Run) par chalti — `CLOUD` env var hi farak (`/chat` response me cloud naam). ACA & Cloud Run = managed serverless containers (CaaS), dono scale-to-zero. Self-demo **in-process TestClient** (koi socket/port nahi). | `uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab2_multicloud_container_deploy.py` (`--serve` = real uvicorn 0.0.0.0:8000, container-jaisa) |
| `lab3_embeddings_sagemaker_vs_bedrock.py` | L74–L78 (ALEX capstone; AWS perms+SageMaker; SageMaker vs Bedrock; deploy embed model; explore) | **Provider-agnostic `get_embeddings()`** 3 backends ke peeche: **SageMaker** (apna model host, all-MiniLM-L6-v2 384-dim, pay-per-hour/use), **Bedrock** (managed titan-embed, pay-per-token), **LocalHashEmbedder** (numpy, offline, $0). `cosine_similarity()` se nearest-neighbour rank = RAG retrieval ka dil. **build-vs-buy**: standard+low-ops → Bedrock; custom/open-source+control → SageMaker. boto3/creds na ho → local-hash. | `uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab3_embeddings_sagemaker_vs_bedrock.py` (`--query "..."` = offline nearest-neighbour) |
| `lab4_vector_ingest_pipeline.py` | L79–L82 (vector pipelines SageMaker+S3; cost-effective S3 Vectors; secure ingest Terraform; E2E test) | **Poora ingest pipeline:** docs → **chunk (with overlap)** → **embed** (LocalHashEmbedder, real = SageMaker/Bedrock lazy boto3) → **pluggable vector store** (`LocalJSONStore` default `./_vectors/`, `S3VectorsBackend` lazy-boto3 stub) → **cosine top-k query**. Plus Lambda-style `handler(event)` (direct `{"text":...}` ya S3-PUT event). **S3 Vectors vs OpenSearch** = ~90% sasta (idle ~$0). | `uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab4_vector_ingest_pipeline.py` (`--one` = ek ingest + ek query) |
| `lab5_rag_research_agent.py` | L83–L86 (research agents; Bedrock+OpenAI SDK; Docker→ECR→App Runner; E2E test) | **RAG loop END-TO-END: retrieve → augment → generate WITH citations.** `research(question)`: embed query → vector store top-k retrieve → chunks ko prompt me augment ("sirf is context se answer do, `[source: id]` cite karo") → LLM grounded answer. **Citations/grounding = trust+audit**. Retrieval = MCP-style tool (`retrieve_context`). LocalHashEmbedder + LocalVectorStore (chromadb lazy). Key na ho → templated grounded answer. | `uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab5_rag_research_agent.py` (`--ask "What is S3 Vectors?"`) |
| `lab6_eventbridge_scheduled_agent.py` | L87–L88 (EventBridge scheduling; Week-3 wrap-up + resilience/cost) | **Scheduled agent = managed cron → Lambda.** EventBridge har N min/hr "wake up" karke Lambda fire karta; `handler(event)` job chalata + summary return. **cron vs rate** expressions; **PUSH (managed, idle $0) vs PULL (always-on box)**; **idempotency** (at-least-once delivery → run-key se duplicate skip); scheduled-event shape (`source=="aws.events"`) API-GW se alag. boto3 na ho → local mock run. | `uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab6_eventbridge_scheduled_agent.py` (`--one` = ek scheduled tick simulate) |

> Note: lecture numbers concept-wise mapping hain. Exact lecture ke liye apne Week3 theory notes ka topic match kar lo.

### Quick start (sab FREE, no cloud, no key, self-demo, exit 0)

```bash
# my-agentic-ai-project root se:
uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab1_cybersecurity_agent_semgrep_triage.py
uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab2_multicloud_container_deploy.py
uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab3_embeddings_sagemaker_vs_bedrock.py
uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab4_vector_ingest_pipeline.py
uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab5_rag_research_agent.py
uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab6_eventbridge_scheduled_agent.py
```

> **lab2 sirf** `--serve` flag rakhta hai (real uvicorn 0.0.0.0:8000 = container-jaisa) — kyunki wahi ek long-running FastAPI workload hai. lab1/3/4/5/6 default run hi self-demo hai (handlers / pipeline / agent in-process invoke karte). Asli HTTP test deploy ke baad cloud URL par `curl` se (Section 3).

---

## 3. Deploy recipes (EXACT commands)

`deploy/` folder me ready:
- `deploy/Dockerfile` — multi-cloud image: `python:3.12-slim` + `uv` + `fastapi/uvicorn/openai/python-dotenv`, `COPY lab2_multicloud_container_deploy.py`, `EXPOSE 8000`, `HEALTHCHECK curl /health`, `CMD uvicorn lab2_multicloud_container_deploy:app --host 0.0.0.0 --port 8000`. **`--platform linux/amd64`** zaroori (niche).
- `deploy/azure_container_app.tf` — `azurerm` provider; RG + Log Analytics workspace + Container App **Environment** + Container App (image, cpu=0.5, mem=1Gi, **min_replicas=0** scale-to-zero, secret `groq-api-key`, `CLOUD=azure` env, ingress `target_port=8000`). Outputs: `app_url`, `resource_group`.
- `deploy/gcp_cloud_run.tf` — `google` provider; `google_cloud_run_v2_service` (image, cpu=1, mem=1Gi, **min_instance_count=0**, `CLOUD=gcp` env, `container_port=8000`) + `iam_member allUsers roles/run.invoker` (public). Outputs: `service_url`, `project_id`.
- `deploy/eventbridge_schedule.tf` — `aws_cloudwatch_event_rule` + `event_target` + `aws_lambda_permission` triple, gated by **`scheduler_enabled` (default `false`)** + `count = var.scheduler_enabled ? 1 : 0`. Outputs: `schedule_status`, `schedule_rule_name`, `schedule_expression_used`.

> **SageMaker endpoint ke liye is folder me alag `.tf` nahi hai** — wo lecture L77 me Terraform se deploy hota (all-MiniLM-L6-v2 serverless endpoint) aur lab3 us endpoint ko **boto3 `sagemaker-runtime.invoke_endpoint()`** se call karta. Niche (3d) uska deploy + **delete-endpoint teardown** CLI se diya hai (yahi Week-3 ka per-hour gotcha).

### (a) Docker image build (saari cloud deploys ka pehla step — PAID nahi, build local)

```bash
# CWD = Practical/ (build context me lab2 file honi chahiye; Dockerfile COPY relative isi se).
cd Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical

# ⚠️ --platform linux/amd64 ZAROORI: Mac (Apple Silicon = ARM) par by-default arm64 banegi,
#    par ACA/Cloud Run amd64 chalate => mismatch par container CRASH (exec format error).
docker build --platform linux/amd64 -t multicloud-agent -f deploy/Dockerfile .

# Local sanity (container ke andar jaisa) — phir Ctrl-C:
docker run --rm --env-file ../../../.env -p 8000:8000 multicloud-agent
curl localhost:8000/health
curl -XPOST localhost:8000/chat -H 'content-type: application/json' -d '{"message":"hi"}'
```

### (b) Azure Container Apps (PAID — TEARDOWN zaroori; deploy/azure_container_app.tf)

```bash
# --- 0) az login + providers register + budget alert (Section 1 & Step 0) done? ---
az login
az group create --name multicloud-agent-rg --location "East US"

# --- 1) ACR (registry) banao + image push (amd64 image, step (a) se) ---
az acr create --resource-group multicloud-agent-rg --name <ACR_NAME> --sku Basic
az acr login --name <ACR_NAME>
ACR_LOGIN=$(az acr show --name <ACR_NAME> --query loginServer -o tsv)
docker tag  multicloud-agent $ACR_LOGIN/multicloud-agent:latest
docker push $ACR_LOGIN/multicloud-agent:latest

# --- 2) Terraform: init -> azure workspace -> plan -> apply ---
cd Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/deploy
terraform init
terraform workspace new azure       # pehli baar (dobara: workspace select azure)
terraform plan  -var "image=$ACR_LOGIN/multicloud-agent:latest" -var "groq_api_key=$GROQ_API_KEY"
terraform apply -var "image=$ACR_LOGIN/multicloud-agent:latest" -var "groq_api_key=$GROQ_API_KEY"

# --- 3) Live URL test ---
APP=$(terraform output -raw app_url)        # https://<...>.azurecontainerapps.io
curl "$APP/health"                          # {"status":"ok",...}
curl -XPOST "$APP/chat" -H 'content-type: application/json' -d '{"message":"hello azure"}'
#  -> response me "cloud":"azure" dikhega (CLOUD env var)

# --- 4) TEARDOWN (Section 0.5 A) — terraform destroy + RG delete + ACR delete ---
```

### (c) GCP Cloud Run (PAID — TEARDOWN zaroori; deploy/gcp_cloud_run.tf)

```bash
# --- 0) gcloud auth (user + ADC) + project + budget alert done? (Section 1 & Step 0) ---
gcloud auth login
gcloud auth application-default login        # Terraform google provider isse creds uthata
gcloud config set project <PROJECT_ID>

# --- 1) Artifact Registry repo + image push (amd64 image, step (a) se) ---
gcloud artifacts repositories create <repo> --repository-format=docker --location <region>
gcloud auth configure-docker <region>-docker.pkg.dev
IMG=<region>-docker.pkg.dev/<PROJECT_ID>/<repo>/multicloud-agent:latest
docker tag  multicloud-agent $IMG
docker push $IMG

# --- 2) Terraform: init -> gcp workspace -> plan -> apply ---
cd Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/deploy
terraform init
terraform workspace new gcp          # pehli baar (dobara: workspace select gcp)
export TF_VAR_project_id=<PROJECT_ID>            # L72 TF_VAR_ convention (variable bina default)
terraform plan  -var "image=$IMG" -var "groq_api_key=$GROQ_API_KEY"
terraform apply -var "image=$IMG" -var "groq_api_key=$GROQ_API_KEY"

# --- 3) Live URL test ---
SVC=$(terraform output -raw service_url)    # https://<...>.run.app
curl "$SVC/health"
curl -XPOST "$SVC/chat" -H 'content-type: application/json' -d '{"message":"hello gcp"}'
#  -> response me "cloud":"gcp" dikhega — WAHI image, sirf CLOUD env alag = parity proof

# --- 4) TEARDOWN (Section 0.5 B) — terraform destroy + service delete + repo delete ---
```

> **Parity proof (L73 ka asli sabak):** (b) aur (c) me **bilkul wahi image** (`multicloud-agent:latest`) deploy hui — sirf `.tf` provider block aur `CLOUD` env var alag. `/chat` response ka `"cloud"` field hi batata kaunsa cloud serve kar raha. Yahi "build once, run anywhere" / "works on my machine" bug ka khatma.

### (d) SageMaker embedding endpoint deploy + 🔴 delete-endpoint TEARDOWN (L77 — per-hour gotcha)

Lab3 ka real path ye endpoint **boto3 `sagemaker-runtime.invoke_endpoint()`** se call karta. Endpoint lecture L77 me Terraform se deploy hota (all-MiniLM-L6-v2, 384-dim, serverless). Yahan deploy + **sabse zaroori cleanup**:

```bash
# --- 0) PEHLE check: koi endpoint chalu to nahi (per-hour bill)? ---
aws sagemaker list-endpoints --region us-east-1     # L75: pehli baar [] hona chahiye

# --- 1) Deploy (L77 Terraform module ya CLI). Pseudo (Ed ka 2_embedding/ module):
#   terraform apply   # aws_sagemaker_model + endpoint_configuration + endpoint
#   => endpoint "alex-embedding-endpoint" InService hota (status check):
aws sagemaker describe-endpoint --endpoint-name alex-embedding-endpoint --region us-east-1

# --- 2) Test invoke (L77: body {"inputs": "text"}) — lab3 isi shape ko boto3 se hit karta:
aws sagemaker-runtime invoke-endpoint \
  --endpoint-name alex-embedding-endpoint \
  --content-type application/json \
  --body '{"inputs":"how do I save for retirement"}' \
  --region us-east-1  /dev/stdout

# --- 3) Lab3 ko REAL SageMaker par point karo (.env / env):
#   SAGEMAKER_ENDPOINT_NAME=alex-embedding-endpoint  (set ho + boto3 + creds => real path,
#   warna LocalHashEmbedder fallback). Phir:
uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab3_embeddings_sagemaker_vs_bedrock.py

# --- 4) 🔴 TEARDOWN — USI DIN, kaam khatam hote hi (per-hour bill idle bhi chalta!) ---
aws sagemaker delete-endpoint        --endpoint-name alex-embedding-endpoint --region us-east-1
aws sagemaker delete-endpoint-config --endpoint-config-name alex-embedding-endpoint --region us-east-1
aws sagemaker delete-model           --model-name alex-embedding-model --region us-east-1
aws sagemaker list-endpoints --region us-east-1     # phir se [] confirm karo
# (Terraform se banaya tha to `terraform destroy` bhi, par list-endpoints se DOBARA verify.)
```

> **Dohraana zaroori:** Lambda/ACA/Cloud Run idle par $0 (scale-to-zero). **SageMaker provisioned endpoint idle par bhi PER-HOUR bill** karta — ye Week-3 ka sabse aam, sabse mehnga bhool. Endpoint banaya = `delete-endpoint` usi session me. (Intermittent ingest ke liye **serverless** endpoint use karo — wo pay-per-use, idle sasta.)

### (e) Bedrock embedding enablement (managed, per-token, deploy se pehle — L76)

```text
1) Console -> Amazon Bedrock -> Model access -> "Manage model access"
2) amazon.titan-embed-text-v2:0 (embeddings) select karo (+ Nova/Claude inference ke liye).
3) Request submit -> aksar instant approve. Region match (us-east-1).
4) BEDROCK_EMBED_MODEL_ID set ho to lab3/lab4 ka get_embeddings Bedrock use karega; warna
   LocalHashEmbedder fallback. Koi API key nahi — IAM role authorize, bill AWS account par.
```

### (f) EventBridge schedule (deploy/eventbridge_schedule.tf — L87; default OFF)

```bash
cd Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/deploy
terraform init

# --- DEFAULT: scheduler_enabled=false => 0 resource banta (automation OFF, $0). ---
terraform plan       # schedule_status = "DISABLED (scheduler_enabled=false)"

# --- ON karna ho (COST-BEARING: har tick research run = Bedrock+SageMaker+S3) ---
terraform apply \
  -var "scheduler_enabled=true" \
  -var 'schedule_expression=rate(2 hours)' \
  -var "research_lambda_arn=arn:aws:lambda:us-east-1:<ACCOUNT_ID>:function:alex-scheduler" \
  -var "research_lambda_name=alex-scheduler"
#  => rule + target + lambda_permission triple banta. (3rd resource bina kiye rule fire hota
#     par invoke AccessDenied — silent gotcha; isliye permission resource zaroori.)

terraform output schedule_status            # "ENABLED"
terraform output schedule_expression_used   # "rate(2 hours)"

# --- TEARDOWN (Section 0.5 E): scheduler_enabled wapas false ya terraform destroy ---
terraform apply -var "scheduler_enabled=false"   # one-line OFF (cost discipline, L88)
```

> **Cost lever (L88):** cadence ghatao — `rate(2 hours)` (din me 12 runs) → `rate(20 hours)`; ya `scheduler_enabled=false` (automation OFF bina code delete kiye). Default already `false` rakha taaki galti se cost ON na ho.

---

## 4. Cost-control box

| Lever | Kya karo | Kyun |
|---|---|---|
| **🔴 SageMaker endpoint** | Banaya = `aws sagemaker delete-endpoint` USI DIN; intermittent ingest ke liye **serverless** endpoint (provisioned nahi); roz `list-endpoints` check | **Provisioned = per-hour, idle bhi bill** — Week-3 ka #1 silent paisa-khaava. ~$43/mo sirf ek idle ml.t2.medium par. |
| **Scale-to-zero (ACA + Cloud Run)** | `min_replicas=0` / `min_instance_count=0` (already set) | Idle par $0. Par **ACR / Artifact Registry storage scale-to-zero NAHI** — alag se delete karo. |
| **Bedrock token caps** | `max_tokens` cap; embeddings titan micro-charge | Per-token, managed (idle $0). Loop/abuse par add-up. |
| **S3 Vectors > OpenSearch** | RAG storage ke liye S3 Vectors / bucket (lab4 default LocalJSONStore) | OpenSearch provisioned ~$50 idle-cost (L79); S3 Vectors idle ~$0 = ~90% sasta (L80). |
| **EventBridge cadence** | `scheduler_enabled=false` (default) ya `rate(2h)`→`rate(20h)` | Har tick = downstream run cost (Bedrock+SageMaker+S3). One-line OFF (L88). |
| **Budget alerts (×3 clouds)** | Deploy se PEHLE AWS + Azure + GCP teeno par (Step 0) | Kisi cloud par **HARD CAP NAHI** — alert hi safety net. |
| **Local-first** | Sab labs boto3/semgrep-lazy + numpy-hash embed + LocalJSONStore + Groq; deploy sirf jab local pakka chale | Cloud par debug = paisa + time waste. LLM/cloud cost $0 jab tak deploy na karo. |
| **TEARDOWN (har stack)** | `terraform destroy` per stack + delete-endpoint + empty S3 + delete ACR/repo + delete-rule + billing check (×3) | Multi-cloud = multi-cleanup. SageMaker per-hour + registry storage + versioned S3 = silent cost. |

> Ed ka pura course estimate: **~$5–$10**, zyaadatar free-tier/credits ke andar. Discipline rakho (Groq local + serverless SageMaker + delete-endpoint same-day + scale-to-zero + scheduler OFF + destroy ×3) to actual spend ~$0–$2.

---

## 5. Common errors & fixes

| Error / symptom | Wajah | Fix |
|---|---|---|
| `[INFO] boto3/AWS not available -> local fallback` / "S3 Vectors unavailable, using LocalJSONStore" | boto3 missing, ya creds nahi, ya `ALEX_VECTOR_BUCKET`/`SAGEMAKER_ENDPOINT_NAME` set nahi | **Expected** local par — labs auto-fallback (LocalHashEmbedder + `./_vectors/`), exit 0. Real chahiye to `uv add boto3` + `aws configure` + env set. |
| `semgrep: command not found` / "semgrep not installed -> mini-scanner" (lab1) | `semgrep` binary/module nahi | **Expected** — lab1 built-in regex/AST mini-scanner par girta (offline, free, findings phir bhi dikhte). Real SAST chahiye to `uv add semgrep` / `brew install semgrep`. |
| `GROQ_API_KEY missing => skipping live call` / templated / placeholder reply | `.env` me `GROQ_API_KEY` nahi | **Expected** — handler/agent shape dikha ke exit 0. Live LLM chahiye to `.env` me `GROQ_API_KEY=gsk_...` (free-tier). |
| **chromadb/numpy present par sentence-transformers NAHI** → embeddings garbage/lexical-only | Real semantic embedder (`all-MiniLM-L6-v2`) install nahi; lab **hash embedder** use kar raha | **By design** — LocalHashEmbedder deterministic + offline (lexical overlap pakadta, synonyms nahi). Real semantic chahiye to SageMaker/Bedrock embed endpoint (3d/3e), ya `sentence-transformers` install (bada download). |
| **🔴 SageMaker endpoint chalu chhod diya → bill badh raha** | Provisioned endpoint per-hour bill karta, idle bhi | **TURANT** `aws sagemaker delete-endpoint --endpoint-name alex-embedding-endpoint`. Roz `aws sagemaker list-endpoints` check karo. (Section 0.5 C / 3d.) |
| Container `exec format error` / cloud par crash (ACA/Cloud Run) | **Image platform mismatch** — Mac (arm64) par build hui, cloud amd64 chalata | `docker build --platform linux/amd64 ...` (Dockerfile note + Section 3a). Rebuild + re-push + re-apply. |
| ACA/Cloud Run **OOM / container restart** | Memory default chhota; app startup spike (L72 memory gotcha) | `.tf` me `memory` badhao (`1Gi`→`2Gi`). gcp file `resources.limits.memory`, azure `template.container.memory`. Sirf default par bharosa mat karo. |
| ACA deploy → `MissingSubscriptionRegistration` / provider not registered | Azure resource providers register nahi | `az provider register --namespace Microsoft.App` + `Microsoft.OperationalInsights` (L68, Section 1). |
| Cloud Run apply → `PERMISSION_DENIED` / `allUsers` IAM set nahi hua | Org policy public access block, ya ADC project galat | `gcloud auth application-default login` + `gcloud config set project`; org policy ho to admin se `iam.allowedPolicyMemberDomains` exception. |
| `terraform` workspace galat resources destroy/create kar raha | Azure aur GCP **same `deploy/` folder** me — workspace switch bhula | `terraform workspace select azure` (ya `gcp`) deploy/destroy se PEHLE. Har cloud apna workspace (L68/L72). |
| EventBridge rule fire hota par Lambda **invoke nahi** (silent) | `aws_lambda_permission` (3rd resource) missing | `eventbridge_schedule.tf` ka triple complete hai confirm; `scheduler_enabled=true` se teeno bante. Bina permission = `events.amazonaws.com` ko invoke ki ijaazat nahi. |
| `AccessDenied` SageMaker/Bedrock/S3 par | IAM scope kam, ya model access nahi maanga | L75 Alex-Access group (SageMakerFullAccess + BedrockFullAccess + S3 Vectors policy); Bedrock Console -> Model access enable (3e). |
| `AuthenticationError`/`401` LLM call par | `OPENAI_API_KEY` me galti se Google key (is `.env` ka quirk — Section 6) | Local ke liye **Groq** rakho (default `get_client("groq")`). Bedrock cloud me (koi key nahi). OpenAI chahiye to asli `sk-...`. |
| `command not found: terraform` / `az` / `gcloud` / `docker` | Tool installed nahi | Section 1 ke install commands (`brew install hashicorp/tap/terraform`, `brew install azure-cli`, `brew install --cask google-cloud-sdk`, Docker Desktop). |
| Galat folder se run | Relative path / build context resolve nahi hua | `uv run ...` hamesha **`my-agentic-ai-project` root** se. `docker build` **`Practical/`** se (`-f deploy/Dockerfile .`). Terraform **`Practical/deploy/`** se. |

---

## 6. `.env` key quirk (zaroor padho)

Is user ke root `.env` me:

```bash
GROQ_API_KEY=gsk_...     # ✅ VALID, free-tier  -> local runs ke liye yahi use karo (preferred)
GOOGLE_API_KEY=...       # ✅ VALID (Gemini ke liye, gemini-2.5-flash)
OPENAI_API_KEY=...       # ⚠️ is .env me yeh actually ek GOOGLE key hold karta hai —
                         #    asli OpenAI key NAHI. Isliye get_client("openai") fail karega.
```

> **Practical advice:** local runs ke liye **hamesha Groq** (`get_client("groq")`, har lab ka default) — free, fast, key valid. Gemini try karna ho to `get_client("gemini")` + `GOOGLE_API_KEY`. **OpenAI tab tak avoid karo** jab tak asli `sk-...` na ho — warna 401. Cloud me ye irrelevant: ACA/Cloud Run me `GROQ_API_KEY` secret/env se inject hoti (image me bake NAHI); Bedrock/SageMaker me **koi API key nahi** — IAM role authorize karta hai.

---

## 7. Order to do them in (aur kyun)

1. **lab1** — Cybersecurity agent (Semgrep + LLM triage): scan-tool + LLM-reasoning division, SAST, MCP-tool shape. (L64–L66)
2. **lab2** — Multi-cloud container: ek image → Azure ACA + GCP Cloud Run, build-once-run-anywhere parity. (L66–L73)
3. **lab3** — Embeddings: `get_embeddings()` ke peeche SageMaker vs Bedrock vs local-hash; cosine = RAG retrieval ka dil; build-vs-buy. (L74–L78)
4. **lab4** — Vector ingest pipeline: chunk+overlap → embed → pluggable store → cosine query + Lambda ingest handler; S3 Vectors vs OpenSearch cost. (L79–L82)
5. **lab5** — RAG research agent: lab3+lab4 jod ke retrieve→augment→generate with citations (grounding/trust). (L83–L86)
6. **lab6** — EventBridge scheduled agent: managed cron → Lambda, push-vs-pull, idempotency, scheduled-event shape. (L87–L88)

> Logic: lab1 cyber-agent + lab2 multi-cloud container = "agent ko package karke kai cloud par chalao" (deployment side). lab3 (embeddings) + lab4 (vector store/pipeline) + lab5 (RAG loop) = "agent ko knowledge do" (data/RAG side). lab6 us pipeline ko **autonomous** (scheduled) banata. Yahi Week-2 (single-cloud serverless) se Week-3 (multi-cloud + apna model host + RAG data plumbing + scheduled automation) ka jump hai.

---

## 8. Week 3 done = milestone

**Week 3 khatam matlab tum ek multi-cloud, RAG-powered AI agent ship kar sakte ho** — jo:
- ek **container workload** ho (FastAPI + Dockerfile) jo **bilkul wahi image** se **Azure Container Apps + GCP Cloud Run + AWS** teeno par chale (build-once-run-anywhere, `CLOUD` env hi farak),
- embeddings ke liye **provider-agnostic `get_embeddings()`** ho jo **SageMaker (self-host) ⇄ Bedrock (managed) ⇄ local-hash** ek config se swap kare (build-vs-buy samajh ke),
- ek **vector ingest pipeline** ho (chunk+overlap → embed → pluggable store → cosine top-k), S3 Vectors par (OpenSearch se ~90% sasta),
- ek **RAG loop** (retrieve→augment→generate **with citations/grounding**) jo hallucination kam kare aur auditable ho,
- **EventBridge se autonomous scheduled** (managed cron, push-not-pull, idempotent, idle $0) ho,
- aur — sabse important — **tumhe pata ho ki SageMaker provisioned endpoint PER-HOUR idle bhi bill karta hai (delete-endpoint same-day), ACA/Cloud Run scale-to-zero hai par ACR/Artifact-Registry storage nahi, teeno clouds par HARD CAP nahi (budget alert ×3 pehle), aur har stack ka teardown (`terraform destroy` per workspace + delete-endpoint + empty S3 + delete registry + delete-rule + billing confirm ×3) kaise karna hai.**

> **Compare against the official repo:** Ed ke exact versions (OpenAI Agents SDK + real Semgrep MCP server, `aws_scheduler_schedule` (newer EventBridge Scheduler) vs is lab ka classic `aws_cloudwatch_event_rule` triple, real all-MiniLM-L6-v2 SageMaker endpoint, App Runner+ECR research deploy, OpenSearch→S3 Vectors migration) ke saath apne labs milao — jahan farak ho wahan samjho kyun (concept same, implementation tumne self-contained + lazy-import + offline-fallback banaya).

---

### TL;DR

```bash
# LOCAL (free): root se koi bhi lab —
uv run Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical/lab2_multicloud_container_deploy.py

# DEPLOY multi-cloud (paid): budget alerts ×3 -> ek image build -> Azure + GCP —
cd Udemy_EdDonner_ProductionTrack/Week3_MultiCloud_SageMaker_Pipelines/Practical
docker build --platform linux/amd64 -t multicloud-agent -f deploy/Dockerfile .
cd deploy && terraform init
terraform workspace select azure && terraform apply -var "image=$ACR_LOGIN/multicloud-agent:latest" -var "groq_api_key=$GROQ_API_KEY"
terraform workspace select gcp   && terraform apply -var "image=$IMG" -var "groq_api_key=$GROQ_API_KEY"

# SAGEMAKER (🔴 per-hour): deploy -> use -> DELETE same-day —
aws sagemaker delete-endpoint --endpoint-name alex-embedding-endpoint --region us-east-1

# TEARDOWN (zaroori, har stack): kaam khatam hote hi —
terraform workspace select azure && terraform destroy -var "image=..." -var "groq_api_key=$GROQ_API_KEY"
terraform workspace select gcp   && terraform destroy -var "image=..." -var "groq_api_key=$GROQ_API_KEY"
# + delete-endpoint + empty/delete S3 + delete ACR/Artifact-Registry + delete-rule + billing ×3
```

Locally sab free me todo. Cloud par tab jao jab ready ho — aur **kaam khatam hote hi `terraform destroy` (har stack) + `delete-endpoint` (SageMaker same-day)** (Section 0.5). Happy shipping. 🚀
