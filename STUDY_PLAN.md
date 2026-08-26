# 📘 STUDY PLAN — The Only File You Need (Zero → Advanced)
# Backend Developer + DevOps + Agentic AI

> **This is the single entry point.** Everything that used to live in `ROADMAP.md`, `COMPULSORY_TOPICS.md`,
> `SENIOR_MUST_READ.md`, and `00_START_HERE.md` now lives here, in one file, in order. Those four files
> are gone — don't look for them, don't recreate them. If you're ever confused about what to study,
> **open this file and nothing else.**
>
> **Two parts:**
> - **PART A — Current Sprint** — the exact day-by-day plan for right now (Day 1–56). Start here if you've
>   already got backend experience (this assumes ~4 yrs Python backend) and are closing specific gaps.
> - **PART B — Full Reference Map** — the complete zero-to-advanced phase list (Phase 0–23). Use this if
>   you want the full basic→advanced picture, need to revisit fundamentals, or want to know what comes
>   after the current sprint ends.
>
> Appendices at the end: a compulsory-topics self-check, and a curated "if you're short on time" reading list.

---

## How to use this file

**One rule:** find the first `- [ ]` in the section you're working through → do exactly that → check it off → move to the next. Never jump ahead. Never re-derive "what should I do today" — it's already decided below.

**Daily routine (2.5–5 hours depending on the phase):**

| Block | Time | What |
|---|---|---|
| Lab / practical first | 1–2 hr | Run the lab / practical file. Where you get stuck IS where the day's theory matters. |
| Theory (as needed) | 1 hr | Open the `.md` file the lab points to, only for the part you got stuck on. |
| Log | 5 min | 3 lines in [`MY_PROGRESS.md`](MY_PROGRESS.md): what you did, what was hard, what's next. |

**Every night, 3 lines in [`MY_PROGRESS.md`](MY_PROGRESS.md).** If the "Kiya" line is empty, that day's progress was zero — no matter how much you read.

---

# 🎯 PART A — CURRENT SPRINT (Day 1–56)

> This is what to actually do, today, in order. It assumes the basics (Part B, Phases 0–10) are already
> familiar — this sprint targets the real remaining gaps: observability, Kubernetes, Terraform/AWS, a
> deployed capstone, system design fluency, messaging depth, and interview polish.
>
> **Roz ka time: ~2.5 ghante** (2h main kaam + 20 min DSA + jo bacha). Kam time ho to sirf 🔴 wala karo, 🟡 skip kar do — par order mat todo.

### Pehle yeh 3 baatein (ek baar padho, phir bhool jao)

**1. Yeh repo padhne ke liye nahi hai — karne ke liye hai.** 1390+ .md files hain. Tumhe saari nahi padhni. Yeh sprint sirf wahi ~120 cheezein sequence karta hai jo interview + job ke liye zaroori hain. Baaki files **reference** hain (Part B) — tab kholna jab lab me atko.

**2. Lab pehle, theory baad me.** Lab shuru karo → jahan atko wahi theory file kholo → wapas lab pe.

**3. Har raat [`MY_PROGRESS.md`](MY_PROGRESS.md) me 3 line.**

### 🚨 RUKO — interview N din me hai?

**Interview scheduled hai to yeh sprint PAUSE karo.** Yeh 8-hafte ka skill-building sequence hai, interview prep nahi. Interview ke 3-5 din pehle sequence chhodo, prep pe jao, phir wapas isi din pe aa jao.

**General interview-week formula** (sprint ki jagah):
1. JD ke top-5 keywords nikalo → repo me unki files kholo (poora topic nahi, sirf 🔴 section — Appendix 1)
2. Har topic **bolke** samjhao — 2 min, bina file dekhe. Atko to wahi padho.
3. Appendix 1 (neeche) se apne tier-🔴 pe self-check
4. Ek DSA problem roz (streak) — [`harness.py`](Backend_Developer/03_Interview_AnyYear/01_DSA/practice/)
5. Interview ke baad: outcome [`JOB_TRACKER.md`](JOB_TRACKER.md) me likho, aur jo nahi aaya wo agla topic

### 🔁 Roz ka parallel track (har din, upar wale kaam ke saath)

| Kya | Time | Kahan | Kyun roz |
|---|---|---|---|
| 🗣️ **English speaking** | 30 min | [`english_speaking/README.md`](english_speaking/README.md) + [awalenglish.com](https://www.awalenglish.com/) course | **Asli gap yahi hai.** Tech aata hai, bolna nahi aata. Internal curriculum + workbook grammar/vocab deta hai; awalenglish speaking practice/feedback — dono complement karte hain. System-design drill *bolke* karo to dono ek saath ho jate hain. |
| 🧮 **DSA** | 20 min | [`01_DSA/practice/`](Backend_Developer/03_Interview_AnyYear/01_DSA/practice/) → `python harness.py` | Coding round pehla filter hai. Streak mat todo — 1 problem bhi chalega. |
| 💼 **Apply** | 15 min | [`JOB_TRACKER.md`](JOB_TRACKER.md) | Padhai khatam hone ka wait mat karo. Apply karte raho. |

---

## 🟢 WEEK 1 — Observability (resume ki sabse badi missing line)

**Kyun pehle:** resume pe Prometheus/Grafana hai hi nahi. Ek hafte me wo *kiya hua* ban jayega.

- [ ] **Day 1** 🔴 Setup + pehla lab — `DevOps/11_Monitoring/practical/01_monitoring_lab.md` → **Lab 1** (Prometheus + Grafana + node_exporter khada karo). Time: 1.5h · Verify: `localhost:9090/targets` pe dono UP dikhein
- [ ] **Day 2** 🔴 Apni app instrument karo — same file → **Lab 2** (RED method — Toofan/Niroskos me `/metrics`, Counter + Histogram, p95 panel). Time: 2h · **sabse important lab poore hafte ka**
- [ ] **Day 3** 🔴 Alerts — same file → **Lab 3** (alert rule + Alertmanager routing). Atko to: `DevOps/11_Monitoring/01_prometheus_grafana_alertmanager.md`
- [ ] **Day 4** 🔴 Debugging scenario — same file → **Lab 4** (cardinality explosion diagnose karo) + Self-Check Checklist. Time: 1.5h
- [ ] **Day 5** 🔴 Logging stack — `DevOps/12_Logging/practical/01_logging_lab.md` → **Lab 1 + 2** (Loki/Promtail, grok filter)
- [ ] **Day 6** 🟡 Logging deep — same file → **Lab 3 + 4** (LogQL, mehnga logging setup diagnose)
- [ ] **Day 7** 🔴 **Resume update karo** — Skills: `Prometheus, Grafana, Loki, PromQL, RED method, p95 SLOs`. Project bullet: *"instrumented X with RED metrics; p95 latency Y ms"*. ✅ Week 1 done

## 🟢 WEEK 2 — Kubernetes (sabse badi skill gap)

- [ ] **Day 8** 🔴 Cluster khada karo + Deployments — `DevOps/06_Kubernetes/practical/01_kubernetes_lab.md` → Prerequisites (minikube/kind) + **Lab 1**
- [ ] **Day 9** 🔴 Same file → **Lab 1 ke steps 5-6** (rolling update + broken image + rollback)
- [ ] **Day 10** 🔴 Same file → **Lab 2** (ConfigMaps, Secrets, StatefulSet)
- [ ] **Day 11** 🔴 Same file → **Lab 3** (Ingress + HPA + RBAC)
- [ ] **Day 12** 🔴 Same file → **Lab 4** (CrashLoopBackOff debug) + Self-Check
- [ ] **Day 13** 🟡 Autoscaling theory — `DevOps/06_Kubernetes/06_cluster_autoscaling_karpenter.md` (HPA vs CA vs Karpenter)
- [ ] **Day 14** 🔴 **Resume update** — `Kubernetes (Deployments, Services, Ingress, HPA, RBAC), Helm`

## 🟢 WEEK 3 — Terraform + AWS (IaC proof)

- [ ] **Day 15** 🔴 `DevOps/08_Terraform/practical/01_terraform_lab.md` → **Lab 1** (S3 bucket provision)
- [ ] **Day 16** 🔴 Same file → **Lab 2** (variables, validation, outputs, workspaces)
- [ ] **Day 17** 🔴 Same file → **Lab 3** (module + remote state backend)
- [ ] **Day 18** 🔴 Same file → **Lab 4** (state drift detect + reconcile) + Self-Check
- [ ] **Day 19** 🔴 **AWS budget alert pehle set karo ($5)**, phir `DevOps/07_Cloud_AWS/practical/01_aws_lab.md` → **Lab 1** (IAM + S3). ⚠️ Har lab ke end me teardown step **chalao**
- [ ] **Day 20** 🔴 Same file → **Lab 2** (2-AZ VPC + subnets) — teardown mat bhoolna
- [ ] **Day 21** 🔴 **Resume update** — `Terraform (modules, remote state), AWS VPC/IAM/ASG`

## 🟢 WEEK 4 — Capstone Deploy (yahi M-2 hai — 3 roles unlock)

- [ ] **Day 22** 🔴 Plan likho: Toofan (ya Niroskos) ko deploy karna hai — architecture 1 page. Reference: `Backend_Developer/01_Year3-4_Mid/04_DevOps/10_fastapi_production_deployment.md`
- [ ] **Day 23** 🔴 Dockerfile production-grade banao (multi-stage, non-root) — `DevOps/05_Docker/practical/01_docker_lab.md` Lab 1 ka pattern use karo
- [ ] **Day 24** 🔴 K8s manifests likho (Deployment + Service + Ingress + ConfigMap/Secret)
- [ ] **Day 25** 🔴 Terraform se infra (EKS ya EC2+K8s, ya managed alternative)
- [ ] **Day 26** 🔴 Monitoring wire karo (Week 1 wala hi setup, ab deployed app pe)
- [ ] **Day 27** 🔴 **Eval harness + cost tracking** agent pe (Agentic role ke liye yahi missing tha). Reference: `Agentic_AI/Level6_Agent_Patterns/10_agent_evaluation.md` + `Agentic_AI/Level8_Production_LLMOps/10_cost_optimization_advanced.md`
- [ ] **Day 28** 🔴 **README likho + resume update + GitHub link**. ✅ **M-2 complete** — roles 3/4/5 (Agentic, Platform, LLMOps) ab open

## 🟡 WEEK 5-6 — System Design (roz ek drill, BOLKE)

> Roz ka format: **1 drill (45 min, bolke) + 1 theory file + DSA**. Bolke karna = English practice bhi saath me. Voice memo record karo.

- [ ] **Day 29** Drill 1: URL Shortener → `Backend_Developer/02_Year5+_Senior/01_System_Design/PRACTICE_DRILLS.md` (Tier 1). Theory: `HLD_Theory/01_Monolithic_vs_Microservices.md`
- [ ] **Day 30** Drill 2: Pastebin · Theory: `HLD_Theory/04_Latency.md` + `05_Throughput.md`
- [ ] **Day 31** Drill 3: Rate Limiter (LLD) · Theory: `HLD_Theory/06_Availability.md`
- [ ] **Day 32** Drill 4: Gaming Leaderboard · Theory: `HLD_Theory/07_Consistency_Strong_vs_Eventual.md`
- [ ] **Day 33** Theory: `HLD_Theory/08_CAP_Theorem.md` + Drill 1 **repeat** (score 15+ badhna chahiye)
- [ ] **Day 34** Theory: `HLD_Theory/12_Load_Balancer.md` + `13_Caching_Complete.md`
- [ ] **Day 35** Theory: `HLD_Theory/20_Database_Indexing.md` + `38_Database_Sharding.md`
- [ ] **Day 36** Drill 5: Twitter/X Feed (Tier 2) · Theory: `HLD_Theory/31_Back_of_Envelope_Estimation.md`
- [ ] **Day 37** Drill 6: WhatsApp Chat · Theory: `HLD_Theory/44_Consistent_Hashing_Theory.md`
- [ ] **Day 38** Drill 7: Uber/Ride Matching · Theory: `HLD_Theory/43_Geohashing.md`
- [ ] **Day 39** Drill 8: BookMyShow · Theory: `HLD_Theory/59_Saga_Pattern.md`
- [ ] **Day 40** Theory: `HLD_Theory/51_Idempotency_Tokens.md` + `65_Dead_Letter_Queue.md`
- [ ] **Day 41** Drill 12: **RAG/LLM Backend** (tumhara differentiator — 2 baar karo)
- [ ] **Day 42** Gap log padho → jo cheez baar-baar miss hui, wo 3 drills me sudhaaro

(All `HLD_Theory/` paths above are relative to `Backend_Developer/02_Year5+_Senior/01_System_Design/`.)

## 🟡 WEEK 7 — Messaging + Data (jo JD me maange, wahi deep)

- [ ] **Day 43** `Backend_Developer/01_Year3-4_Mid/07_Kafka/labs/README.md` → setup + **Lab 1, 2**
- [ ] **Day 44** Kafka labs → **Lab 3, 4** (ordering, manual commit redelivery)
- [ ] **Day 45** Kafka labs → **Lab 5** (consumer lag) + `08_ordering_guarantees.md`
- [ ] **Day 46** `Backend_Developer/01_Year3-4_Mid/09_Celery/labs/README.md` → **Lab 1, 2** (states, retries)
- [ ] **Day 47** Celery labs → **Lab 3, 4** (routing/canvas, acks_late crash)
- [ ] **Day 48** `Backend_Developer/00_Year0-2_Junior/04_Database_SQL/07_postgresql_internals.md` (MVCC/WAL/VACUUM)
- [ ] **Day 49** `Backend_Developer/00_Year0-2_Junior/04_Database_SQL/21_isolation_levels_anomalies.md` + `13_postgresql_performance_tuning.md`

## 🟡 WEEK 8 — Interview Polish

- [ ] **Day 50** `Backend_Developer/03_Interview_AnyYear/02_Interview_Prep/05_backend_system_design_50q.md`
- [ ] **Day 51** `.../02_Interview_Prep/07_python_tricky_questions.md` + `08_sql_interview_questions.md`
- [ ] **Day 52** `.../02_Interview_Prep/09_debugging_scenarios.md`
- [ ] **Day 53** `.../02_Interview_Prep/11_resume_walkthrough_prep.md` — **apna resume bolke walk karo, record karo**
- [ ] **Day 54** `.../02_Interview_Prep/10_behavioral_backend.md` — STAR format me 5 kahaniyan likho
- [ ] **Day 55** `.../02_Interview_Prep/12_negotiation_offer.md`
- [ ] **Day 56** `Agentic_AI/Interview_Prep/01_system_design_ai_questions.md` — AI-role wale sawaal. ✅ **Interview-ready**. Ab apply karna shuru karo (agar pehle nahi kiya).

## ⏱️ Roz ka parallel track (Day 1 se hi shuru, 20 min)

- [ ] DSA: `cd Backend_Developer/03_Interview_AnyYear/01_DSA/practice && python3 harness.py` — roz **1 problem**, order me. 35 problems = 35 din. Week 5-6 tak khatam ho jayenge. Target: Day 35 tak 35/35 attempted, Day 49 tak 35/35 passing.

## 🔵 Week 8 ke baad — role ke hisaab se (yahan pehli baar choice hai)

Tab tak tumhe pata hoga kis role pe interviews aa rahe hain:

| Agar target hai | To ab yeh |
|---|---|
| **Senior Backend** | `Backend_Developer/01_Year3-4_Mid/05_Microservices/` (poora) + `Backend_Developer/01_Year3-4_Mid/15_Design_Patterns_SOLID/Section_10_Interview_Drills/` |
| **GenAI/Agentic** | `Agentic_AI/Level6_Agent_Patterns/` (13 docs) + `Agentic_AI/Level8_Production_LLMOps/` |
| **Platform/LLMOps** | `DevOps/` ke bache hue phases (Ansible, CI/CD, Security) + `Agentic_AI/Modern_Topics/23_claude_agent_sdk_skills.md` |
| **Koi bhi** | `Agentic_AI/Modern_Topics/23_claude_agent_sdk_skills.md` + `24_openai_agentkit.md` |

After Week 8+, drop into Part B below for anything not covered by the sprint — it has the full picture, phase by phase.

---

# 📚 PART B — FULL REFERENCE MAP (Zero → Advanced, Phase 0–23)

> The complete basic-to-advanced picture, one phase at a time. Use this if you're starting genuinely
> from zero, want to revisit a fundamental, or want to know what's beyond the current sprint (Part A).
> Rule: `[ ]` = not done. `[x]` = done. Pick the FIRST unchecked item in your current phase, never jump ahead.

---

## PHASE 0 — Terminal & Internet Basics
> "Before writing code, know the machine you are sitting on." Location: `DevOps/`

- [x] `DevOps/01_Linux/01_linux_basics.md` — what is Linux, file system, users
- [x] `DevOps/01_Linux/02_essential_commands.md` — ls, cd, cat, grep, find, chmod
- [x] `DevOps/01_Linux/03_file_compression.md` — tar, zip, gzip
- [x] `DevOps/01_Linux/04_process_management.md` — ps, kill, top, htop
- [x] `DevOps/01_Linux/05_disk_management.md` — df, du
- [x] `DevOps/01_Linux/06_networking_commands.md` — ping, curl, netstat, ss
- [x] `DevOps/01_Linux/07_services_systemd.md` — start/stop/enable services
- [x] `DevOps/01_Linux/practical/01_linux_lab.md` — **HANDS-ON LAB**
- [x] `DevOps/03_Networking/01_osi_tcpip_fundamentals.md` — how internet works, OSI layers
- [x] `DevOps/03_Networking/02_protocols.md` — HTTP, HTTPS, TCP, UDP, DNS
- [x] `DevOps/03_Networking/03_web_concepts.md` — request/response, ports, status codes
- [x] `DevOps/03_Networking/practical/01_networking_lab.md` — **HANDS-ON LAB**
- [x] `DevOps/04_Git/01_git_deep_dive.md` — init, add, commit, push, pull, branch, merge
- [x] `DevOps/04_Git/practical/01_git_lab.md` — **HANDS-ON LAB**

**Done when:** You can navigate the terminal, understand what HTTP is, and commit code to git.

## PHASE 1 — Python Absolute Basics
> Location: `Backend_Developer/00_Year0-2_Junior/`

- [ ] `01_Foundations/06_environment_setup_complete.md` — install Python, venv, pip
- [ ] `02_Python_Daily/Day01_Variables_Basics/` — all files (variables, types, operators, ATM calculator)
- [ ] `02_Python_Daily/Day02_Control_Flow_Loops/` — all files (if/elif/else, for, while, break/continue, number-guessing game)
- [ ] `02_Python_Daily/Day03_String_Problems/` — all files (strings, palindrome, anagram)
- [ ] `02_Python_Daily/Day04_Lists_Arrays/` — all files
- [ ] `02_Python_Daily/Day05_Dictionary_Problems/` — all files
- [ ] `02_Python_Daily/Day06_Sets_Tuples/` — all files
- [ ] `02_Python_Daily/Day07_Functions_Recursion/` — all files
- [ ] `02_Python_Daily/Complete_Practical/Section_01_Basics/` — 01 through 06 (variables/types → exceptions)

**Done when:** You can write Python scripts to solve basic problems — loops, functions, lists, dicts.

## PHASE 2 — Python Intermediate
> Location: `Backend_Developer/00_Year0-2_Junior/02_Python_Daily/`

- [ ] `Day08_OOP_Classes_Inheritance/` — class, `__init__`, inheritance, `super()`
- [ ] `Day09_OOP_Dunder_Encapsulation/` — `__str__`, `__repr__`, private attributes
- [ ] `Day10_Decorators_Generators_Collections/` — @decorator, yield, Counter, defaultdict
- [ ] `Day11_Algorithms_Complexity/` — Big O, binary search, sorting
- [ ] `Day12_Exception_Handling/` — try/except/finally, custom exceptions
- [ ] `Day15_FileIO_Functional/` — read/write files, lambda, map, filter
- [ ] `Complete_Practical/Section_02_Intermediate/01_oop_complete.py` + `02_iterators_generators_context.py`
- [ ] `Complete_Theory/01_Core_Python_Theory.py` + `02_Functions_Closures_Decorators_Theory.py` + `03_OOP_Theory.py`
- [ ] `Backend_Developer/00_Year0-2_Junior/01_Foundations/05_first_api_in_plain_english.md` — what is an API
- [ ] `01_Foundations/08_postman_api_testing.md` — test APIs with Postman

**Done when:** You can write classes, use decorators, handle exceptions, and read/write files.

## PHASE 3 — Python Concurrency + SQL Basics
> Location: `Backend_Developer/00_Year0-2_Junior/`

- [ ] `02_Python_Daily/Day13_Threading_Multiprocessing/` — threads vs processes, GIL
- [ ] `02_Python_Daily/Day14_Async_Python/` — async/await, event loop, asyncio
- [ ] `02_Python_Daily/Day16_Functools_Itertools_Dataclasses/`
- [ ] `02_Python_Daily/Complete_Practical/Section_02_Intermediate/03_async_complete.py` + `04_threading_multiprocessing.py`
- [ ] `02_Python_Daily/Complete_Theory/04_Async_Concurrency_Theory.py`
- [ ] `01_Foundations/07_sql_fundamentals_standalone.md` — SELECT, INSERT, UPDATE, DELETE, JOIN
- [ ] `04_Database_SQL/practical/` — write real SQL queries
- [ ] `05_MySQL/theory/` + `05_MySQL/practical/` — MySQL-specific, connect Python to MySQL

> **Parallel from here:** start DSA — see Phase 21 below, 1 problem/day alongside everything.

**Done when:** You can write async Python, write SQL queries, connect to a database.

## PHASE 4 — First Real Backend API
> Location: `Backend_Developer/00_Year0-2_Junior/`

- [ ] `04_Database_SQL/00_postgresql_start_here.md` — PostgreSQL not MySQL
- [ ] `06_FastAPI/practical/` — routes, request/response, path/query params
- [ ] `02_Python_Daily/Day44_FastAPI/` + `Day45_SQLAlchemy_Alembic/` + `Day47_Pydantic_v2/`
- [ ] `06_FastAPI/labs/` — build a full CRUD API
- [ ] `07_Django_DRF/practical/` — models, views, serializers, auth
- [ ] `02_Python_Daily/Day43_ArgParse_Typer/` — CLI tools

**Done when:** You have a working REST API with CRUD operations and user authentication.

## PHASE 5 — DevOps Basics (Bash + Docker)
> Location: `DevOps/`

- [ ] `DevOps/02_Bash_Scripting/01_bash_fundamentals.md` + `02_automation_cron_scripting.md` + `practical/01_bash_lab.md`
- [ ] `DevOps/05_Docker/01_docker_basics.md` → `02_dockerfile.md` → `03_docker_compose.md` → `04_storage_networking_registry.md` → `practical/01_docker_lab.md`
- [ ] `Backend_Developer/00_Year0-2_Junior/02_Python_Daily/Day49_Docker/` — Dockerize your FastAPI app

**Done when:** Your app runs inside Docker with a docker-compose.yml that starts app + database together.

## PHASE 6 — Redis, Caching & Testing
> Location: `Backend_Developer/00_Year0-2_Junior/`

- [ ] `08_Redis/theory/` + `08_Redis/practical/` + `08_Redis/labs/`
- [ ] `02_Python_Daily/Day46_Celery_Redis/`
- [ ] `09_Caching/theory/` + `09_Caching/practical/`
- [ ] `10_Testing/theory/` + `10_Testing/practical/` + `02_Python_Daily/Day41_Testing/`

**Done when:** Your API has a Redis caching layer and a test suite that passes.

## PHASE 7 — Python Advanced (Deep Mastery)
> Location: `Backend_Developer/00_Year0-2_Junior/02_Python_Daily/`

- [ ] `Day17_Asyncio_Advanced_ABC/` through `Day42_Enum_Datetime_OS/` (Day17–42, minus days already covered) — MRO, DSA-pattern intro (Day20-25), Collections/Functools/Itertools, Typing deep dive, Logging/Pathlib/dotenv, context managers, dataclasses advanced, metaclasses/descriptors, profiling/memory
- [ ] `Day48_gRPC_Protobuf/` · `Day50_Contextvars/` · `Day51_Concurrency_Senior/` · `Day52_Inspect_Module/`
- [ ] `Day53_GapFill_Core_Part1/` + `Part2` · `Day54_GapFill_Advanced/` · `Day55_GapFill_Concurrency_Memory/`
- [ ] `Complete_Practical/Section_03_Advanced/` — 01 typing → 02 design patterns → 03 internals/performance
- [ ] `Complete_Theory/05_...Theory.py` through `10_Regex_Testing_Enum_StdLib_Theory.py`

**Done when:** You understand metaclasses, memory model, GIL, typing system, all stdlib tools.

## PHASE 8 — Mid-Level Backend (APIs, Security, Messaging)
> Location: `Backend_Developer/01_Year3-4_Mid/`

- [ ] `01_Python_Advanced/theory/` + `practical/` + `Interview_Handson_Practice/` — GIL internals, async deep dive, memory
- [ ] `02_API_Design/practical/` — versioning, pagination, rate limiting, idempotency, webhooks
- [ ] `03_Security/practical/` — JWT, OAuth2, RBAC, HTTPS, OWASP Top 10
- [ ] `06_gRPC/practical/` + `labs/` — Protocol Buffers, gRPC server/client
- [ ] `07_Kafka/practical/` + `labs/` — topics, partitions, consumer groups, exactly-once (see Part A Week 7 for the exact lab sequence when you're doing this as part of the sprint)
- [ ] `08_RabbitMQ/theory/` + `practical/` + `exercises/` — exchanges, routing, durability
- [ ] `09_Celery/theory/` + `practical/` + `labs/` — task queues, beat scheduler, workers
- [ ] `Backend_Developer/00_Year0-2_Junior/11_File_Handling/practical/` — file uploads, S3 presigned URLs
- [ ] `Backend_Developer/00_Year0-2_Junior/12_Email_Notifications/practical/` — SMTP, transactional email

**Done when:** You can build secure, event-driven APIs with background task processing.

## PHASE 9 — NoSQL Databases + Real-time Features
> Location: `Backend_Developer/01_Year3-4_Mid/`

- [ ] `10_MongoDB/theory/` + `practical/` — documents, collections, aggregation pipeline
- [ ] `11_Elasticsearch/theory/` + `practical/` — full-text search, mappings, queries
- [ ] `12_GraphQL/practical/` — schemas, resolvers, N+1 problem, DataLoader
- [ ] `13_WebSocket_SSE/practical/` — real-time bidirectional communication

**Done when:** You can choose the right database for a use case and build real-time features.

## PHASE 10 — Design Patterns + Engineering Practices
> Location: `Backend_Developer/01_Year3-4_Mid/`

- [ ] `15_Design_Patterns_SOLID/Section_01` through `Section_10` — foundations → SOLID → code smells → creational/structural/behavioral → Python idioms vs GoF → backend mapping → anti-patterns → interview drills
- [ ] `14_Engineering_Practices/labs/` — code review, clean code, CI practices
- [ ] `05_Microservices/practical/` — decomposition, CQRS, event sourcing, saga pattern

**Done when:** You recognise patterns in existing code and write clean, testable, maintainable code.

## PHASE 11 — DevOps Advanced (Kubernetes + AWS + Terraform + CI/CD)
> Location: `DevOps/` — **this is Part A's Weeks 1–3 in full reference form; if you're mid-sprint, use Part A's day-by-day version instead.**

- [ ] `DevOps/06_Kubernetes/01` through `06` (architecture/objects → networking/ingress → storage/config/secrets → scaling/RBAC → Helm → Karpenter autoscaling) + `practical/01_kubernetes_lab.md`
- [ ] `DevOps/07_Cloud_AWS/01` through `05` (IAM/EC2 → storage/DB → networking/DNS/LB → ECS/EKS → monitoring/messaging/secrets) + `practical/01_aws_lab.md`
- [ ] `DevOps/07_Cloud_Azure/01_azure_fundamentals.md` + `02_azure_devops_python.md` + `practical/01_azure_lab.md`
- [ ] `DevOps/10_CICD/01_jenkins.md` → `02_github_actions.md` → `03_gitlab_ci_delta.md` → `04_gitops_argocd.md` + `practical/01_cicd_lab.md` + `practical/02_gitops_lab.md`
- [ ] `DevOps/08_Terraform/01_terraform_iac.md` + `practical/01_terraform_lab.md`
- [ ] `DevOps/09_Ansible/01_ansible_config_mgmt.md` + `practical/01_ansible_lab.md`

**Done when:** You have your app deployed on AWS/EKS with a CI/CD pipeline that auto-deploys on git push.

## PHASE 12 — DevOps Observability + Security
> Location: `DevOps/` — **this is Part A's Week 1 in full reference form.**

- [ ] `DevOps/11_Monitoring/01_prometheus_grafana_alertmanager.md` + `practical/01_monitoring_lab.md`
- [ ] `DevOps/12_Logging/01_elk_loki_fluentd.md` + `practical/01_logging_lab.md`
- [ ] `DevOps/13_Web_Servers/01_nginx.md` + `02_apache_basics.md` + `practical/01_web_servers_lab.md`
- [ ] `DevOps/14_Security/01_ssh_ssl_tls_hardening.md` + `practical/`
- [ ] `DevOps/15_Databases/practical/` · `16_Messaging_Systems/practical/` · `17_Caching/practical/`
- [ ] `DevOps/18_System_Design/practical/` · `19_Observability/practical/` · `20_Best_Practices/practical/`
- [ ] `DevOps/21_Projects/` — full DevOps project end to end

**Done when:** You have Prometheus + Grafana monitoring, ELK logging, and Nginx with SSL running.

## PHASE 13 — AI & ML Foundations
> Location: `Agentic_AI/Level1_LLM_Foundations/`

- [ ] `Classical_ML_DL_Foundations/01` through `12` — regression → perceptron/MLP → loss/activation → gradient descent/backprop → deep NN → CNN → RNN/LSTM → RNN-limits/transformer-bridge → transfer learning → GANs/diffusion → classical ML algos → classical NLP pipeline
- [ ] `01_what_is_an_llm.md` → `02_tokens_embeddings.md` → `03_history_of_llms.md` → `04_attention_transformers.md` → `05_models_landscape.md` → `06_dev_environment_setup.md` → `07_first_api_calls.md` (+practical) → `08_world_models_theory_of_mind.md`

**Done when:** You understand how neural networks learn, what attention is, and you've made your first LLM API call.

## PHASE 14 — Transformer Deep Architecture
> Location: `Agentic_AI/Level1_LLM_Foundations/Deep_Architecture/`

- [ ] `00_complete_journey.md` → `01_request_flow.md` → `02_tokenization_deep.md` → `03_embeddings_and_position.md` → `04_attention_complete.md` → `05_transformer_block.md` → `06_layer_stacking_and_output.md` → `07_sampling_and_generation.md` → `08_inference_optimizations.md` → `09_training_briefly.md` → `10_visualize_internals_practical.py`

**Done when:** You can explain how a transformer generates text token by token.

## PHASE 15 — Prompt Engineering
> Location: `Agentic_AI/Level2_Prompt_Engineering/`

- [ ] All 10 files in order (`01_anatomy_of_prompt.md` → `10_anti_patterns.md`), each with its `_practical.py`

**Done when:** You can write prompts that reliably extract what you need, understand system prompts, roles, temperature, structured output.

## PHASE 16 — LLM APIs & SDKs
> Location: `Agentic_AI/Level3_LLM_APIs_SDKs/`

- [ ] All 11 files in order (`01_openai_api_complete.md` → `11_azure_openai.md`), each with its `_practical.py`

**Done when:** You can call any LLM API, handle streaming, retries, and extract structured data reliably.

## PHASE 17 — Tool Use + RAG
> Location: `Agentic_AI/Level4_Tool_Use_Function_Calling/` and `Level5_RAG_Vector_Databases/`

- [ ] All files in `Level4_Tool_Use_Function_Calling/` in order (`.md` + `_practical.py`)
- [ ] All files in `Level5_RAG_Vector_Databases/` in order (`.md` + `_practical.py`)

**Done when:** You've built a chatbot that searches documents and calls real APIs; you understand chunking, embeddings, hybrid search, reranking.

## PHASE 18 — Agent Patterns + Frameworks
> Location: `Agentic_AI/Level6_Agent_Patterns/` and `Level7_Frameworks/`

- [ ] `Level6_Agent_Patterns/01` through `13` — patterns, ReAct, plan-execute, memory, reflection, multi-agent supervisor, routing, HITL, evaluation, swarm, harness engineering, context engineering
- [ ] `Level7_Frameworks/01_langchain_complete.md` → `02_langgraph_complete.md` (**most important**) → `03_langgraph_advanced.md` → `04_mcp_complete.md` (**most important**) → `05_crewai_complete.md` → `06_dspy_complete.md` → `07_llamaindex.md` → `08_pydantic_ai.md` → `09_semantic_kernel.md` → `10_a2a_protocol.md` → `11_haystack.md`

**Done when:** You can build a multi-agent system using LangGraph where agents collaborate to complete a complex task.

## PHASE 19 — Production AI (LLMOps)
> Location: `Agentic_AI/Level8_Production_LLMOps/` and `Modern_Topics/`

- [ ] `Level8_Production_LLMOps/01` through `11` — production AI, LLMOps, testing, enterprise platforms, GraphRAG, fine-tuning, specialized AI, observability, guardrails, cost, Databricks/Spark/Snowflake
- [ ] `Modern_Topics/00` through `10` — tools landscape, voice agents, computer use, local serving, memory frameworks, multimodal, browser automation, AI coding tools, MCP server dev, AI security, AI ethics
- [ ] `Modern_Topics/23_claude_agent_sdk_skills.md` + `24_openai_agentkit.md`

**Done when:** You can deploy an AI system to production with monitoring, guardrails, and cost controls.

## PHASE 20 — System Design (Senior Level)
> Location: `Backend_Developer/02_Year5+_Senior/` — **for the drill-based day-by-day version, use Part A Weeks 5-6.**

- [ ] `01_System_Design/HLD_Theory/` — all 67 files in order (2 per day)
- [ ] `01_System_Design/LLD_Theory/` — SOLID + all design pattern docs
- [ ] `01_System_Design/HLD_Problems/` — URL Shortener, Twitter, YouTube, Uber, WhatsApp, Netflix, Rate Limiter, ChatGPT backend (practice out loud)
- [ ] `01_System_Design/LLD_Problems/` — LRU Cache, Parking Lot, Rate Limiter, Elevator, Payment System
- [ ] `01_System_Design/HLD_Code/` — CQRS, event sourcing, saga, circuit breaker code
- [ ] `01_System_Design/Design_Patterns_Code/` — 16 Django mini-projects implementing patterns
- [ ] `02_Architecture_Patterns/` — event-driven, microservices, serverless patterns
- [ ] `03_Senior_Leadership/` — tech debt, engineering ladder, RFC/ADR writing

**Done when:** You can design any system end-to-end in a 45-minute whiteboard session, out loud.

## PHASE 21 — DSA (Data Structures & Algorithms)
> Note: start this in parallel from Phase 3 onwards — 1 problem daily alongside everything else.
> Location: `Backend_Developer/03_Interview_AnyYear/01_DSA/`

- [ ] `00_Coding_Patterns_Index.md` — read first, understand the 28 patterns
- [ ] Patterns 1–9: Two Pointers, Sliding Window, Fast & Slow, Stack/Monotonic, Hashing/Prefix Sum, Intervals, Binary Search, Trees BFS/DFS, Graphs BFS/DFS
- [ ] Patterns 10–19: Heaps, DP basics, DP advanced, Greedy, Trie, Topological Sort, Union-Find, Backtracking/Subsets, String DP, Bit Manipulation
- [ ] Patterns 20–28: advanced patterns (segment tree, suffix structures, digit DP, bitmask DP — FAANG-tier only)

## PHASE 22 — Capstone Projects (Build Real Things)
> "Prove you can build, not just read." Location: `Agentic_AI/Projects/`

- [ ] `project1_personal_ai_assistant_starter/` — Phase 15-16 level: chat assistant with memory
- [ ] `project2_rag_document_qa_starter/` — Phase 17 level: RAG-based document Q&A
- [ ] `project3_multiagent_code_review_starter/` — Phase 18 level: LangGraph multi-agent system
- [x] `project4_production_ai_saas_starter/` — **COMPLETE** — support-ticket triage agent: `app/agent/triage.py` (agent loop, read-only tools), `app/guardrails.py` (input+output guards), `app/observability/trace.py` (tracing), `app/evals/` (16-case dataset + reliability + mutation suite). Run: `python main.py --provider stub eval` (16/16), `reliability --runs 8` (8/8), `mutation` (0 survivors), `demo "..."`. **Remaining milestones:** multi-tenant DB model + API key hashing, auth middleware, per-tier rate limiting, LiteLLM router with fallback, FastAPI surface, Stripe subscription + webhooks.
- [ ] `project5_wedding_transformation_agent/` — creative agent project
- [ ] `Backend_Developer/03_Interview_AnyYear/03_Projects/` — backend portfolio projects
- [ ] `DevOps/21_Projects/` — end-to-end infrastructure project

> **The capstone that's actually load-bearing right now:** `Agentic_AI/my-agentic-ai-project/Udemy_EdDonner_ProductionTrack/Week4_MultiAgent_Observability_AgentCore/Practical/` — **ALEX**, the multi-agent financial planner. See its [README](Agentic_AI/my-agentic-ai-project/README.md) for the architecture. It's well-documented but not yet actually deployed with a live eval score + cost number — that's the real remaining execution gap, and it's exactly what Part A Week 4 (Capstone Deploy) is for.

## PHASE 23 — Interview Preparation
> Location: `Backend_Developer/03_Interview_AnyYear/` and `Agentic_AI/Interview_Prep/` — **see Part A Week 8 for the day-by-day version.**

- [ ] `Backend_Developer/03_Interview_AnyYear/02_Interview_Prep/` — all 8 files: Python tricky questions, 50 System Design Qs, SQL questions, coding patterns cookbook, behavioral (STAR), resume walkthrough, salary negotiation, mock interview format
- [ ] `Agentic_AI/Interview_Prep/` — all 12 files: system design (AI), coding patterns, behavioral, key technical concepts, role-specific prep, frameworks, databases, async/queues, cloud/DevOps, APIs/security, Python deep dive

---

### PHASE SUMMARY TABLE

| Phase | Track | Topic | Roughly when |
|---|---|---|---|
| 0 | DevOps | Linux + Git + Networking | Week 1 |
| 1 | Backend | Python basics | Week 1 |
| 2 | Backend | OOP, exceptions, files | Week 2 |
| 3 | Backend | Async, SQL, MySQL | Week 3 |
| 4 | Backend | FastAPI + Django first API | Week 4–5 |
| 5 | DevOps | Bash + Docker | Week 5–6 |
| 6 | Backend | Redis + Testing | Week 6–7 |
| 7 | Backend | Advanced Python | Week 7–10 |
| 8 | Backend | Security, gRPC, Kafka, RabbitMQ, Celery | Week 10–13 |
| 9 | Backend | MongoDB, Elasticsearch, GraphQL | Week 13–14 |
| 10 | Backend | Design Patterns, SOLID, Microservices | Week 14–16 |
| 11 | DevOps | Kubernetes + AWS + Terraform + CI/CD | *current sprint Weeks 2-3* |
| 12 | DevOps | Monitoring, Logging, Security | *current sprint Week 1* |
| 13 | AI | Classical ML/DL + LLM Basics | Week 21–23 |
| 14 | AI | Transformer Deep Architecture | Week 23–24 |
| 15 | AI | Prompt Engineering | Week 24–25 |
| 16 | AI | LLM APIs & SDKs | Week 25–26 |
| 17 | AI | Tool Use + RAG | Week 26–28 |
| 18 | AI | Agent Patterns + Frameworks | Week 28–31 |
| 19 | AI | Production LLMOps + Modern Topics | Week 31–33 |
| 20 | Backend | System Design (HLD + LLD) | *current sprint Weeks 5-6* |
| 21 | DSA | Algorithms — 1/day from Phase 3 | Ongoing, parallel |
| 22 | All | Capstone Projects | *current sprint Week 4* |
| 23 | All | Interview Prep + Mock Sessions | *current sprint Week 8* |

---

# ✅ APPENDIX 1 — Compulsory Topics Self-Check

> **Purpose:** the "what MUST I know" coverage map for the product-company switch. If a 🔴 topic below can't be explained out loud in English in 2 minutes, it's a hole to close before you interview.
> 🔴 **COMPULSORY** (every interview touches this) · 🟡 **SHOULD-KNOW** (~70% of roles) · ⚪ **JD-SPECIFIC** (only if named)

### 🔴 Tier 1 — Backend core
- **Python Core + Advanced:** OOP/MRO/dunder, ABC vs Protocol, decorators/closures, generators/iterators, context managers, comprehensions/itertools/functools, threading vs multiprocessing vs asyncio, the GIL, async/await + event loop, dataclasses/`__slots__`/descriptors, type hints + mypy/ruff, exceptions, memory/GC basics
- **DSA:** Arrays/Hashing/Strings/Two-Pointers/Sliding-Window, Stack/Queue/Linked-List/Binary-Search, Recursion/Backtracking/Sorting, Trees/Heaps, Graphs (BFS/DFS/topo/Dijkstra), DP/Greedy/Intervals, Bit Manipulation/Trie, Big-O out loud. ⚠️ **Your weakest gate — daily, from now, target ~150 problems.**
- **Web Framework (go deep on one):** FastAPI (Pydantic v2, `Depends`, async endpoints/background tasks/lifespan, params/status/errors, middleware/CORS/auth/rate-limit) OR Django+DRF (MVT, ORM/migrations/querysets/N+1 fix, middleware/signals, serializers/ViewSets/routers, auth/permissions/throttling/pagination)
- **REST API Design:** verbs/idempotency/status codes, resource naming, versioning, pagination, RFC 7807 errors, JWT/session/API-key/OAuth2, rate limiting, idempotency keys, HATEOAS
- **Databases & SQL:** joins/GROUP BY/subqueries/window-functions/CTEs, indexing (B-tree, composite/covering), transactions/ACID/isolation-levels/anomalies, locking/deadlocks, MVCC/WAL/VACUUM, normalization, N+1, connection pooling, migrations, SQL vs NoSQL
- **Caching & Redis:** data structures, cache-aside/write-through/write-behind, TTL/eviction, stampede/Redlock, pub/sub
- **Testing:** pytest/fixtures/parametrize/mocking, unit vs integration vs e2e, coverage, TDD, testing async — **and a real test suite in your proof-project**
- **System Design:** load balancing/caching/replication/sharding/CAP, message queues, consistency models, capacity estimation, LLD/SOLID/patterns, walk a design out loud
- **Git & Fundamentals:** branching/merge vs rebase/PRs, HTTP/HTTPS/TLS/DNS, Linux basics

### 🔴 Tier 1 (AI) — Agentic AI core
- **LLM APIs & SDKs:** chat completions, streaming, temperature/top_p, structured outputs, retries
- **Prompt Engineering:** zero/few-shot, CoT, role prompting, templates, guardrails
- **Tool Use/Function Calling:** schemas, call→execute→return loop, parallel calls
- **RAG & Vector DBs:** embeddings, chunking, hybrid search, reranking, RAG-vs-fine-tune
- **Agent Patterns:** ReAct, plan-and-execute, reflection, multi-agent, memory, eval basics

### 🟡 Tier 2 — Should-know (~70% of roles)
Security (OWASP/JWT/OAuth/secrets) · DevOps (Docker/CI-CD/K8s) · Observability (logging/Prometheus/OTel) · Microservices (saga/circuit-breaker/Raft idea) · Async tasks (Celery) · Messaging (Kafka/RabbitMQ) · Design Patterns & SOLID · GraphQL · WebSocket/SSE · Agentic Frameworks (LangGraph/MCP/PydanticAI) · Production LLMOps · Engineering Practices (code review/incident response/RFC-ADR)

### ⚪ Tier 3 — JD-specific only
gRPC · MongoDB · Elasticsearch · MySQL specifics (Galera/NDB) · Classical ML/DL foundations · Modern AI (voice/computer-use/multimodal) · Architecture patterns (CQRS/event-sourcing) · Senior leadership

### 🎤 The hidden compulsory topic: English + Storytelling
Not a folder — the delivery layer. Every 🔴 topic above needs to be explainable **out loud in clear English**, tied to a **STAR story** from real work or your proof-project. Practice via [`english_speaking/03_Advanced/06_interview_english.md`](english_speaking/03_Advanced/06_interview_english.md) + weekly mocks.

**How to use:** weekly, scan the 🔴 list — anything you can't say out loud, schedule it in Part A above. Before each interview, read the target JD, promote any ⚪ items it names to 🔴 for that week.

---

# 🎓 APPENDIX 2 — Short On Time? These 22 Files First

> Out of ~1,300 files, these are the ones a senior interview is most likely to actually probe. "Done" means you can answer the linked question out loud, in 2 minutes, without opening the file.

## 🐍 Python internals (4)
| File | Question it answers |
|---|---|
| [Memory model + GIL](Backend_Developer/01_Year3-4_Mid/01_Python_Advanced/theory/03_memory_gil.md) | "GIL kya hai? Threads se CPU work fast kyun nahi hota?" |
| [Async concurrency deep dive](Backend_Developer/01_Year3-4_Mid/01_Python_Advanced/theory/05_async_concurrency_deep_dive.md) | "Event loop kaise kaam karta hai? Blocking call daal do to?" |
| [Concurrency decision framework](Backend_Developer/01_Year3-4_Mid/01_Python_Advanced/theory/26_concurrency_decision_framework.md) | "threading vs multiprocessing vs asyncio — kab kya?" |
| [Race conditions debugging](Backend_Developer/01_Year3-4_Mid/01_Python_Advanced/theory/11_race_conditions_debugging.md) | "Production me race condition kaise pakda?" (needs a real story) |

## 🗄️ Database — most marks here (6)
| File | Question it answers |
|---|---|
| [PostgreSQL internals — MVCC/WAL/VACUUM](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/07_postgresql_internals.md) | "UPDATE karne pe andar kya hota hai? VACUUM kyun chahiye?" |
| [Isolation levels + anomalies](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/21_isolation_levels_anomalies.md) | "Dirty / non-repeatable / phantom read — example do" |
| [Advanced indexing](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/20_advanced_indexing.md) | "Index laga hai phir bhi slow — kyun?" |
| [Optimistic vs pessimistic locking](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/19_optimistic_pessimistic_locking.md) | "Do user ek hi seat book kar rahe hain — kya karoge?" |
| [Connection pooling / pgBouncer](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/11_pgbouncer_connection_pooling.md) | "1000 concurrent users, 100 DB connections — kaise?" |
| [Zero-downtime migrations](Backend_Developer/00_Year0-2_Junior/04_Database_SQL/24_zero_downtime_migrations.md) | "Live table pe column rename karna hai — steps?" |

## 🏗️ System design core (5)
| File | Question it answers |
|---|---|
| [CAP theorem](Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/08_CAP_Theorem.md) | "CP vs AP — apne system me kya chuna aur kyun?" |
| [Back-of-envelope estimation](Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/31_Back_of_Envelope_Estimation.md) | *Every* design round's first 5 minutes |
| [Caching complete](Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/13_Caching_Complete.md) | "Cache kahan lagaoge, invalidate kaise karoge?" |
| [Database sharding](Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/38_Database_Sharding.md) | "Ek table 500GB ka ho gaya — ab?" |
| [Load balancer](Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/12_Load_Balancer.md) | L4 vs L7, algorithms, health checks |

## 🧩 Distributed systems (4)
| File | Question it answers |
|---|---|
| [Outbox pattern](Backend_Developer/01_Year3-4_Mid/05_Microservices/04_outbox_event_sourcing.md) | "DB commit ho gaya par event publish fail — kya karoge?" ← **the most discriminating question** |
| [Distributed systems theory](Backend_Developer/01_Year3-4_Mid/05_Microservices/10_distributed_systems_theory.md) | Partial failure, consensus, "network reliable nahi hai" |
| [Saga pattern](Backend_Developer/02_Year5+_Senior/01_System_Design/HLD_Theory/59_Saga_Pattern.md) | "3 service me transaction — 2PC ke bina kaise?" |
| [Idempotency + testing](Backend_Developer/01_Year3-4_Mid/09_Celery/theory/10_testing_idempotency.md) | "Task/API do baar chal gaya to?" |

## 🔐 Security + API (3)
| File | Question it answers |
|---|---|
| [OAuth2 flows deep + OIDC](Backend_Developer/01_Year3-4_Mid/03_Security/04_oauth2_flows_deep.md) | "OAuth2 vs OIDC?" · "PKCE kyun?" |
| [JWT vulnerabilities](Backend_Developer/01_Year3-4_Mid/03_Security/03_jwt_vulnerabilities_2fa_secrets.md) | "JWT revoke kaise karoge?" · `alg: none` |
| [Idempotency + conditional requests](Backend_Developer/01_Year3-4_Mid/02_API_Design/18_conditional_requests_deep.md) | "Payment API retry ho gaya — double charge rokoge kaise?" |

### If you have more time — Tier 2 (24 files) and Tier 3 (14 files) exist too:
Python code-quality (metaclasses/descriptors, modern 3.11-3.13, SOLID) · API design (versioning, rate limiting, webhooks, REST-vs-GraphQL-vs-gRPC) · data/scale (partitioning, EXPLAIN tuning, consistent hashing) · caching patterns/stampede/Redlock · events/messaging (Kafka ordering, exactly-once, CQRS, DLQ) · architecture (DDD, anti-patterns, observability/resilience) · production ops (OTel, SRE SLI/SLO, incident response) — plus staff-track extras: thread-safety war stories, DI/Repository/State-Machine, session/secrets management, K8s+Helm, Prometheus+Grafana (labs, not just reading), pytest advanced + Testcontainers, RFC/ADR + tech strategy + DORA metrics, debugging scenarios/resume walkthrough/code review.

**AI/GenAI role too?** Add just 3: [RAG advanced](Agentic_AI/Level5_RAG_Vector_Databases/02_rag_advanced.md) (biggest file, core of any RAG design round) · [Agent harness engineering](Agentic_AI/Level6_Agent_Patterns/12_agent_harness_engineering.md) · [LLMOps production](Agentic_AI/Level8_Production_LLMOps/02_llmops_production.md).

**Not enough on its own:** reading these 22 (or 60) files doesn't make you senior — being able to **say them out loud, unscripted** does. Every file above has its question written next to it for exactly this reason.

---

## PROGRESS TRACKING

Update [`MY_PROGRESS.md`](MY_PROGRESS.md) every night with 3 lines:
```
DATE: 2026-08-26
DONE: Week 1 Day 3 — Prometheus alert rules + Alertmanager routing
HARD: cardinality explosion took a while to diagnose
TOMORROW: Day 4 — the debugging lab
```

## CONFUSION RULE

If you feel lost, stuck, or don't know what to do next:
1. Open **this file**
2. If mid-sprint: find the first `- [ ]` in Part A
3. Otherwise: find the first `- [ ]` in your current Part B phase
4. Do exactly that one thing. Nothing else.

**One file. Start to end. No more searching across multiple plans.**

---

**Related (different purpose, not merged here):** [`MY_PROGRESS.md`](MY_PROGRESS.md) (daily log) · [`JOB_TRACKER.md`](JOB_TRACKER.md) (application pipeline) · [`INTERVIEW_PREP_COMPANIES.md`](INTERVIEW_PREP_COMPANIES.md) (company-specific prep) · [`JD_ANALYSIS_TOP50.md`](JD_ANALYSIS_TOP50.md) (market data) · [`Agentic_AI/MASTER_INDEX.md`](Agentic_AI/MASTER_INDEX.md) (Agentic track full index)
