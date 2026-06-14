# PRACTICAL_RUNBOOK.md — Week 1 Hands-On Guide (Hinglish)

Ye runbook **AI Engineer Production Track** (Ed Donner) ke **Week 1** ka practical/deploy guide hai — Vercel + Full-stack streaming + Auth/Billing + AWS + Docker. Theory notes (L01–L31 ke topics) tumne padh liye honge; ab actual labs chalana, locally todna, aur **cloud par deploy** karna hai.

Tum experienced Python backend dev ho, to FastAPI/HTTP basics skip — yahan asli focus **production/deployment** hai: serverless (Vercel), full-stack streaming (SSE), auth/subscription gating (JWT), containerization (Docker), aur cloud (AWS ECR + App Runner).

> **Sabse important baat (do baar padho):** labs ko **locally chalana 100% FREE hai** — `uv run ...`, Groq free-tier, sab `$0`. Par jab tum **CLOUD par deploy** karoge, to wahan **paisa lag sakta hai** — khaaskar AWS (App Runner + ECR paid hain). Vercel ka hobby tier free hai, AWS nahi. Niche **COST WARNING + TEARDOWN** section dhyaan se padho.

---

## ⚠️ COST WARNING + TEARDOWN (sabse pehle padho)

Ye ek **deployment course** hai. Local sab free hai, par cloud do alag duniya hai:

| Platform | Cost reality | Rule |
|---|---|---|
| **Local** (`uv run`, Docker build/run) | **$0** — tumhari machine ke resources, Groq free-tier | Jitna chaaho chalao, todo. |
| **Vercel** (Hobby plan) | Hello-world / chhoti app par **effectively $0** | Free hai, par fir bhi unused project remove kar dena clean habit hai. |
| **AWS** (ECR + App Runner) | **PAID** — pennies-to-dollars/month. App Runner ¼ vCPU + 0.5GB poora mahina chale to ~**$1–$5/month**; ECR storage chhota charge. | **AWS par koi HARD SPEND CAP nahi hota** — sirf budget *alerts*. Kaam khatam = **TURANT TEARDOWN**. |

> **AWS ka sabse bada gotcha:** App Runner ek **always-on container** chalata hai — chahe koi request aaye ya na aaye, idle bhi paisa katega. Isliye 2 din me kaam karke chhod do to ~$0; bhool gaye to bill chupke se badhta rahega.

### Step 0 — AWS Budget alert SET karo (L24) — deploy se PEHLE

AWS par jaane se pehle ek **zero-spend + monthly budget** banao taaki surprise bill na aaye:

```bash
# Console: Billing & Cost Management -> Budgets -> Create budget
#   - "Zero spend budget" template (alert jaise hi $0.01 cross ho)
#   - + ek monthly cost budget e.g. $5, threshold 80% par email alert
# Apne email par alert aayega — yahi tumhara safety net hai.
```

### Step 0.5 — TEARDOWN commands (kaam khatam hote hi chalao)

Ye commands **zaroori** hain. AWS ko bhoolna = recurring bill.

```bash
# ---- AWS App Runner service delete (sabse zaroori — yahi 24x7 paisa khaata hai) ----
aws apprunner list-services --region <REGION>
aws apprunner delete-service \
  --service-arn <SERVICE_ARN> \
  --region <REGION>

# ---- ECR repository delete (--force => images ke saath delete) ----
aws ecr delete-repository \
  --repository-name production-ai-app \
  --force \
  --region <REGION>

# ---- IAM user delete (jo deploy ke liye banaya tha) ----
# Pehle uski access keys + attached policies hatao, fir user delete:
aws iam list-access-keys --user-name prod-deployer
aws iam delete-access-key --user-name prod-deployer --access-key-id <AKIA...>
aws iam list-attached-user-policies --user-name prod-deployer
aws iam detach-user-policy --user-name prod-deployer --policy-arn <POLICY_ARN>
aws iam delete-user --user-name prod-deployer

# ---- Vercel project remove (free tha, par clean rakho) ----
vercel project rm <project-name>        # ya: vercel remove <deployment-url>

# ---- FINAL: Billing console me confirm karo ----
# Console -> Billing & Cost Management -> Bills -> dekho App Runner/ECR ka
# charge ruk gaya. Budget alert email bhi 1-2 din me settle ho jayega.
```

> **Mantra:** *Deploy karo, dekho, screenshot lo, TEARDOWN karo.* Cloud ko apni padhai ka demo-stage samjho, permanent ghar nahi.

---

## 1. Practical kaise karein — the Learning Loop

Har lab ke liye ye 7-step loop follow karo:

1. **Watch** — Ed ka lecture dekho (theory note ke topic se match karke).
2. **Read note** — Week1 ke matching Hinglish theory note ka topic padho (L01–L31).
3. **Open lab** — `Practical/` folder ka matching `labN_*.py` file kholo, uska docstring header padho (har lab me "kya seekhenge" + "kaise chalana" + "COST" likha hai).
4. **Run (self-demo)** — `uv run ...` se **bina args** chalao. Har lab default me ek **TestClient self-demo** chalata hai — koi server, koi browser, koi API key nahi, exit 0. Baseline dekho.
5. **Run (--serve)** — `--serve` flag se asli uvicorn server launch karo (`http://127.0.0.1:8000`), `/docs` ya `curl` se interactively hit karo.
6. **Tweak / experiment** — prompt badlo, `max_tokens` cap badlo, ek route add karo, fir dobara run karo — farak dekho.
7. **Deploy (jab ready ho)** — niche **Deploy recipes** se Vercel/Docker/AWS par bhejo, fir **TEARDOWN** karo.

> Rule of thumb: pehle **locally** (free) sab samjho — `--serve` + `curl` + `/docs`. Cloud deploy sirf tab jab local pakka chal raha ho. Cloud par debug karna = paisa + time dono waste.

---

## 2. Lab → Lecture → Concept → Run Command map

Saare commands **`my-agentic-ai-project` root** se chalao (jahan `pyproject.toml` / `uv` setup hai). Default run = self-demo (free, no key, exit 0). `--serve` add karo to real server `http://127.0.0.1:8000` par.

| Lab file | Lectures | Kya concept sikhata hai | Run command |
|---|---|---|---|
| `lab1_instant_deploy.py` | L01–L03 (instant deploy, zero→live, AI-as-DevOps) | **Serverless deploy foundation** — minimal FastAPI app (`/`, `/health`, `/info`), koi LLM nahi. `vercel.json` ka `builds`+`routes` request ko module tak kaise laata hai; Deployment Protection (pehla deploy private kyun). | `uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab1_instant_deploy.py` |
| `lab2_llm_api_cost.py` | L06–L08 (live AI app + cost mgmt) | **LLM behind a production API + COST control** — server-side LLM proxy (key kabhi browser me nahi), Pydantic validation, `response.usage` token tracking, `max_tokens` cap, model tiering. `/health`, `/models`, `POST /generate`. | `uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab2_llm_api_cost.py` |
| `lab3_fullstack_streaming.py` | L09–L14 (FE/BE arch, Next.js stack, SSE streaming) | **Full-stack streaming** — token-by-token LLM ko browser tak **SSE** se push (`StreamingResponse` + `stream=True`). Self-contained HTML+JS frontend `EventSource` se `/stream` hit karta hai. Perceived latency win. | `uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab3_fullstack_streaming.py` |
| `lab4_auth_subscription_gating.py` | L15–L18 (Clerk auth + subscription billing) | **Auth + subscription gating (backend half)** — zero-dep JWT (HS256) khud sign+verify, `exp` check; `require_user` (401 = authN) vs `require_pro` (403 = authZ). `/token`, `/me`, `/premium`. No LLM. | `uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab4_auth_subscription_gating.py` |
| `lab5_healthcare_saas.py` | L19–L22 (first commercial app, structured prompts, deploy SaaS) | **Week-1 PROJECT — deployable AI SaaS** — structured prompting (Pydantic JSON schema), defensive parsing (never 500), aur ek **deterministic safety guardrail** (disclaimer code me hard-wired, LLM par depend nahi). `/health`, `POST /assess`. | `uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab5_healthcare_saas.py` |
| `lab6_containerize_for_aws.py` | L23–L31 (AWS/IAM, budgets, Docker, ECR, App Runner) | **Containerize for AWS** — 12-factor config (env vars), ultra-light `/health` (App Runner probe target), graceful no-key fallback. `uvicorn` `0.0.0.0:8000` par bind. Yahi app ECR + App Runner par jaata hai. `/`, `/health`, `/version`, `POST /generate`. | `uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab6_containerize_for_aws.py` |

> Note: lecture numbers concept-wise mapping hain. Exact lecture ke liye apne Week1 theory notes ka topic match kar lo.

### `--serve` option + curl examples

Har lab ko **real server** ke roop me chalane ke liye `--serve` add karo (foreground uvicorn, Ctrl+C se stop). Default port `127.0.0.1:8000`.

```bash
# Lab 1 — instant deploy app (no LLM)
uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab1_instant_deploy.py --serve
curl http://127.0.0.1:8000/                 # {"message":"live from production"}
curl http://127.0.0.1:8000/health           # {"status":"ok"}
# browser: http://127.0.0.1:8000/docs        (Swagger UI)

# Lab 2 — LLM behind production API + cost
uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab2_llm_api_cost.py --serve
curl http://127.0.0.1:8000/models
curl -X POST http://127.0.0.1:8000/generate \
     -H "Content-Type: application/json" \
     -d '{"prompt":"What is a production API gateway?","max_tokens":64}'

# Lab 3 — full-stack streaming (SSE). Browser me / kholo + "Stream it" dabao,
# ya curl -N (no-buffer) se SSE events live dekho:
uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab3_fullstack_streaming.py --serve
curl -N "http://127.0.0.1:8000/stream?prompt=hello"

# Lab 4 — auth + subscription gating (JWT). Pehle token mint karo, fir use karo:
uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab4_auth_subscription_gating.py --serve
TOKEN=$(curl -s -X POST "http://127.0.0.1:8000/token?plan=pro" | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl http://127.0.0.1:8000/me      -H "Authorization: Bearer $TOKEN"   # 200, claims
curl http://127.0.0.1:8000/premium -H "Authorization: Bearer $TOKEN"   # 200 (pro); free token => 403
curl http://127.0.0.1:8000/me                                          # 401 (no header)

# Lab 5 — healthcare info SaaS (structured + guardrail)
uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab5_healthcare_saas.py --serve
curl -X POST http://127.0.0.1:8000/assess \
     -H "Content-Type: application/json" \
     -d '{"symptoms":"mild sore throat and runny nose","age":30,"duration":"2 days"}'

# Lab 6 — containerize-for-AWS app (yahi Docker/ECR/App Runner par jaata hai)
uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab6_containerize_for_aws.py --serve
curl http://127.0.0.1:8000/health            # {"status":"healthy"}
curl http://127.0.0.1:8000/version           # APP_VERSION env se
curl -X POST http://127.0.0.1:8000/generate -H "Content-Type: application/json" -d '{"prompt":"hi"}'
```

> Port busy ho (`address already in use`) to pichla server band karo: `lsof -i :8000` -> PID kill. Ya code me `port=8001` set kar lo.

---

## 3. Deploy recipes (EXACT commands)

Sab kuch `deploy/` folder me ready hai:
- `deploy/instant.py` — Vercel ke liye shippable lab1 app (TestClient/uvicorn imports ke bina, lightweight).
- `deploy/vercel.json` — `builds` (`@vercel/python`) + `routes` (catch-all `/(.*)` -> `instant.py`).
- `deploy/requirements-vercel.txt` — `fastapi` + `uvicorn` (Vercel `requirements.txt` naam padhta hai).
- `deploy/Dockerfile` — `python:3.12-slim`, layer-cached pip install, `curl` HEALTHCHECK, `CMD uvicorn lab6_containerize_for_aws:app --host 0.0.0.0 --port 8000`.
- `deploy/.dockerignore` — `.env`, `.venv`, `__pycache__`, `*.md` etc. context se bahar (image chhoti + secrets bake na ho).
- `deploy/requirements-docker.txt` — `fastapi`, `uvicorn`, `openai`, `python-dotenv`.

### (a) Vercel deploy — lab1 (FREE, hobby tier)

```bash
# 1) deploy/ folder me jao aur Vercel ko requirements.txt ke roop me file do:
cd Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/deploy
cp requirements-vercel.txt requirements.txt    # Vercel @vercel/python `requirements.txt` padhta hai

# 2) Vercel CLI install (ek baar) + login:
npm i -g vercel
vercel login                                   # Google/GitHub/email — jo signup kiya

# 3) Current folder deploy karo:
vercel .                                        # prompts: scope, project name -> Production URL milega

# 4) Verify:
curl https://<your-project>.vercel.app/health   # {"status":"ok"}
```

> **Deployment Protection OFF karo (L02):** pehla deploy by-default **PRIVATE** hota hai (sirf logged-in team dekh sakti hai). Public karne ke liye:
> **Vercel dashboard -> apna project -> Settings -> Deployment Protection -> "Vercel Authentication" toggle OFF -> Save.**
> Fir **incognito window** me URL kholke confirm karo ki bina login ke `live from production` dikh raha hai.

### (b) Docker build + run locally — lab6 (FREE)

Build context **`Practical/`** hai (lab file wahan, requirements `deploy/` me), isliye `-f deploy/Dockerfile` use karte hain.

```bash
cd Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical

# Build (local arch):
docker build -f deploy/Dockerfile -t prodai .

# Run (port map; optional env vars):
docker run -p 8000:8000 prodai
#   key bhi pass karni ho:  docker run -p 8000:8000 -e GROQ_API_KEY=$GROQ_API_KEY -e APP_VERSION=1.2.3 prodai

# Verify (doosre terminal me):
curl http://localhost:8000/health            # {"status":"healthy"}
curl http://localhost:8000/version
```

> **Apple Silicon (M1/M2/M3) gotcha (L29):** AWS App Runner ko `linux/amd64` chahiye. Local par bhale `arm64` me build karo, par **ECR ke liye** explicitly amd64 build karo:
> `docker build --platform linux/amd64 -f deploy/Dockerfile -t prodai .`

### (c) AWS path — lab6 (PAID — TEARDOWN zaroori!)

> Placeholders: `<REGION>` (e.g. `us-east-1`), `<ACCOUNT_ID>` (12-digit AWS account number).

```bash
# --- 1) IAM user banao (LEAST-PRIVILEGE: sirf ECR + App Runner ki zaroorat) (L23/L25) ---
# Root account se kabhi deploy mat karo. Ek dedicated user banao:
aws iam create-user --user-name prod-deployer
aws iam create-access-key --user-name prod-deployer    # AccessKeyId + SecretAccessKey note karo
# Least-privilege: ECR + App Runner ki managed policies attach karo (broad AdministratorAccess avoid).
aws iam attach-user-policy --user-name prod-deployer \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser
aws iam attach-user-policy --user-name prod-deployer \
  --policy-arn arn:aws:iam::aws:policy/AWSAppRunnerFullAccess

# --- 2) CLI configure (us new user ki keys daalo) ---
aws configure        # Access Key, Secret, default region=<REGION>, output=json

# --- 3) ECR repository banao ---
aws ecr create-repository --repository-name production-ai-app --region <REGION>

# --- 4) Docker login to ECR, tag, push (amd64 build!) ---
aws ecr get-login-password --region <REGION> \
  | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com

# Build for amd64 (App Runner requirement), tag with ECR URI:
docker build --platform linux/amd64 -f deploy/Dockerfile \
  -t <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/production-ai-app:latest .
docker push <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/production-ai-app:latest

# --- 5) App Runner service from ECR image (L30) ---
# Console (aasaan): App Runner -> Create service -> Source = "Container registry"
#   -> Amazon ECR -> select production-ai-app:latest
#   -> Port = 8000
#   -> Health check: Protocol=HTTP, Path=/health, Interval=20s, Timeout=5s
#   -> (optional) Environment variables: GROQ_API_KEY=..., APP_VERSION=1.2.3
#   -> Create & deploy.
# Deploy hone par ek live URL milega:  https://<random>.<REGION>.awsapprunner.com

# --- 6) Verify ---
curl https://<random>.<REGION>.awsapprunner.com/health     # {"status":"healthy"}
curl https://<random>.<REGION>.awsapprunner.com/version
```

> **CRITICAL:** App Runner ab idle me bhi paisa khaa raha hai. Demo dekhne/screenshot ke baad **upar wala Step 0.5 TEARDOWN turant chalao** (`delete-service` + `delete-repository --force` + IAM user delete + billing confirm).

---

## 4. Free-tier / cost-control strategy (cost-control box)

| Lever | Kya karo | Kyun |
|---|---|---|
| **Local default = Groq free** | Saare labs default `get_client("groq")` -> `GROQ_API_KEY` free-tier | LLM token cost `$0`, fast, OpenAI-compatible (sirf `base_url` alag). |
| **OpenAI use karna ho** | Cheap model `gpt-4o-mini` rakho, `gpt-4o` sirf hard reasoning ke liye | Model tiering = sabse bada cost lever. 90% traffic mini par chal jaata hai. |
| **`max_tokens` cap** | Har LLM call par output limit (lab2 default 256, lab6 default 120) | Output tokens sabse mehenge; cap = ek call ki worst-case cost bounded. |
| **AWS budgets** | Deploy se PEHLE zero-spend + monthly budget alert (L24, Section Step 0) | AWS par hard cap nahi hota — alert hi tumhara safety net hai. |
| **TEARDOWN** | App Runner + ECR delete karo kaam ke baad | Always-on container = recurring bill. 2 din me hatao = ~$0. |
| **Vercel hobby** | Chhoti app free; deploy karke verify karo, fir unused project remove | $0, par clean rakhna achhi habit. |

> Ed ka pura course estimate: **~$5–$10**, zyaadatar AWS-side. Agar discipline rakho (Groq local + caps + teardown) to actual spend ~$0–$2.

---

## 5. Common errors & fixes

| Error / symptom | Wajah | Fix |
|---|---|---|
| `[INFO] GROQ_API_KEY missing => skipping live call` / "key missing, skipping live call" | `.env` me `GROQ_API_KEY` nahi | **Expected** — labs khud-skip karke exit 0 dete hain (lab2/lab5/lab6). Live LLM output chahiye to `.env` me `GROQ_API_KEY=gsk_...` add karo. |
| Vercel deploy par `requirements.txt not found` / Python build fail | Vercel `requirements.txt` naam dhoondta hai, humare paas `requirements-vercel.txt` hai | `deploy/` me `cp requirements-vercel.txt requirements.txt` chalao, fir `vercel .`. `vercel.json` ka `builds.src` = `instant.py` se match hona chahiye. |
| Vercel URL par login screen / 401 | Deployment Protection (Vercel Authentication) ON (pehla deploy private) | Dashboard -> Settings -> Deployment Protection -> Vercel Authentication **OFF** -> Save (L02). Incognito me verify. |
| `docker: ... port is already allocated` / `address already in use :8000` | Pichla server/container 8000 par chal raha | `lsof -i :8000` se PID kill, ya `docker run -p 8001:8000 ...`. Purana container: `docker ps` -> `docker stop <id>`. |
| App Runner service **Unhealthy** -> container baar-baar replace | Health check fail. App `0.0.0.0:8000` par nahi, ya `/health` me LLM/DB call kar raha (5s timeout), ya Port mismatch | (1) `CMD` me `--host 0.0.0.0 --port 8000` confirm karo (127.0.0.1 sirf local). (2) `/health` ultra-light rakho (koi LLM/DB nahi). (3) App Runner Port=8000, Path=`/health` set karo (L30). |
| `exec format error` / App Runner image start nahi hota | Apple Silicon par `arm64` image push kar di | `docker build --platform linux/amd64 ...` se rebuild + re-push (L29). |
| `Unable to locate credentials` / AWS calls 403 | `aws configure` nahi kiya, ya galat IAM keys | `aws configure` me `prod-deployer` ki Access Key + Secret + `<REGION>` daalo. `aws sts get-caller-identity` se verify. |
| ECR `docker push` -> `denied` / `no basic auth credentials` | ECR login expire/missing | `aws ecr get-login-password ... | docker login ...` dobara chalao (token short-lived hota hai). |
| `AuthenticationError`/`401` LLM call par | `OPENAI_API_KEY` me galti se Google key (is `.env` ka quirk — Section 7) | Local ke liye **Groq hi rakho** (`get_client("groq")`). OpenAI chahiye to ek asli `sk-...` key set karo. |
| `command not found: uv` / `vercel` / `docker` | Tool installed nahi | `uv`: https://docs.astral.sh/uv/ ; `vercel`: `npm i -g vercel` ; Docker Desktop install + running. |
| Galat folder se run | Relative path `Udemy_EdDonner_ProductionTrack/...` resolve nahi hua | Hamesha **`my-agentic-ai-project` root** se `uv run` chalao. Docker build **`Practical/`** se. |

---

## 6. Order to do them in (aur kyun)

1. **lab1** — serverless deploy ka foundation (no AI). Vercel par pehla "live from production". (L01–L03)
2. **lab2** — ek LLM ko production API ke peeche wrap karo + cost knobs (token tracking, `max_tokens`, model tiering). (L06–L08)
3. **lab3** — full-stack streaming: token-by-token SSE se browser tak push. (L09–L14)
4. **lab4** — auth + subscription gating: JWT verify, `require_user` (401) vs `require_pro` (403). (L15–L18)
5. **lab5** — Week-1 **PROJECT**: deployable AI SaaS (structured output + hard-wired safety guardrail). (L19–L22)
6. **lab6** — containerize for AWS: Dockerfile, ECR, App Runner, 12-factor config, health checks. (L23–L31)

> Logic: lab1 deploy-pipeline seekhata hai, lab2–lab5 us pipeline par chhadhne layak production AI app banate hain, lab6 unhe Docker + AWS tak le jaata hai (Vercel PaaS -> AWS IaaS ka trade-off).

---

## 7. `.env` key quirk (zaroor padho)

Is user ke root `.env` me:

```bash
GROQ_API_KEY=gsk_...     # ✅ VALID, free-tier  -> local runs ke liye yahi use karo
GOOGLE_API_KEY=...       # ✅ VALID (Gemini ke liye, gemini-2.5-flash)
OPENAI_API_KEY=...       # ⚠️ is .env me yeh actually ek GOOGLE key hold karta hai —
                         #    asli OpenAI key NAHI. Isliye get_client("openai") fail karega.
```

> **Practical advice:** local runs ke liye **hamesha Groq** (`get_client("groq")`, default) rakho — free, fast, aur key valid hai. Gemini try karna ho to `get_client("gemini")` + `GOOGLE_API_KEY` (valid). **OpenAI tab tak avoid karo** jab tak ek asli `sk-...` key set na karo — warna 401 milega kyunki yahan `OPENAI_API_KEY` me Google key padi hai.

---

## 8. Week 1 done = milestone

**Week 1 khatam matlab tum ek production AI app deploy kar sakte ho** — jo:
- Vercel par serverless deploy ho (Deployment Protection ke saath public/private toggle samajhte ho),
- ek LLM ko cost-aware API ke peeche wrap kare (token tracking + `max_tokens` cap + model tiering),
- browser tak SSE se token-by-token stream kare,
- JWT se authenticate + subscription plan se gate kare,
- Docker me containerize ho aur AWS ECR + App Runner par live chale (health checks + 12-factor config),
- aur — sabse important — **tumhe pata ho cloud par kya free hai, kya paid hai, aur kaam ke baad TEARDOWN kaise karna hai.**

> **Compare against the official repo:** Ed ke exact versions (Next.js frontend + Clerk + AWS steps) ke saath apne labs milao — jahan farak ho wahan samjho kyun (concept same, implementation tumne self-contained banaya).

---

### Quick start (abhi shuru karna ho to)

```bash
# my-agentic-ai-project root se (sab FREE, no key, self-demo, exit 0):
uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab1_instant_deploy.py
uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab2_llm_api_cost.py
uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab3_fullstack_streaming.py
uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab4_auth_subscription_gating.py
uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab5_healthcare_saas.py
uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab6_containerize_for_aws.py
```

Locally sab free me todo. Cloud par tab jao jab ready ho — aur **kaam khatam hote hi TEARDOWN** (Section 0.5). Happy shipping. 🚀
