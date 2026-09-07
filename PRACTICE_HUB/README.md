# Practice Hub — every hands-on lab/project, one place, topic-wise

This directory is **symlinks only** — no files were moved or copied. Every
entry below points at its real location inside `Backend_Developer/`,
`Agentic_AI/`, or `DevOps/`. That means:
- Nothing in the original repo broke (docker-compose paths, cross-links from
  `MASTER_INDEX.md`/`STUDY_PLAN.md`/other labs, git history — all untouched).
- Editing a file here edits the real file (symlinks aren't copies).
- `git status`/`git add` here tracks the symlink itself, not its target's
  content — the target repo paths are still the source of truth.

**Scope:** only genuinely hands-on content — a `labs/`/`exercises/`/`practice/`
folder with real code (or a docker-compose you actually run), or a fleshed-out
project starter with real app code, not a reference-only script or a 3-file
skeleton. Reference `.md` theory and single-file "reference" practicals stay
in their home folders — this hub is for *doing*, not reading.

---

## 01. Fundamentals

| Topic | Path | What it is |
|---|---|---|
| DSA | [DSA](01_Fundamentals/DSA) | Self-checking practice harness — 28 canonical problems, write your own solution, `python harness.py` gives PASS/FAIL + the failing case |
| FastAPI | [FastAPI](01_Fundamentals/FastAPI) | 5 TODO-stub labs: DI/DB sessions, JWT auth, async SQLAlchemy CRUD, background-task idempotency, RFC7807 errors |
| Django DRF | [Django_DRF](01_Fundamentals/Django_DRF) | 5 labs on the real wired Django project (blog/chat/users apps) |
| SQL / Database | [SQL_Database](01_Fundamentals/SQL_Database) | TODO→run→PASS/FAIL SQL exercises |

## 02. Data & Messaging

| Topic | Path | What it is |
|---|---|---|
| Redis | [Redis](02_Data_Messaging/Redis) | docker-compose + 5 labs: cache-aside, stampede lock (20 real racing threads), WATCH/atomic transfer, sliding-window rate limiter, Redlock |
| Kafka | [Kafka](02_Data_Messaging/Kafka) | docker-compose (KRaft broker + kafka-ui) + 5 labs: produce/consume, consumer groups, key-partitioning/ordering, manual-commit crash redelivery, consumer lag |
| RabbitMQ | [RabbitMQ](02_Data_Messaging/RabbitMQ) | docker-compose + 8 exercises with `verify.py` self-checks: fanout, RPC, DLX/retry, topic routing, idempotent consumer, etc. |
| Celery | [Celery](02_Data_Messaging/Celery) | docker-compose (Redis + Flower) + 4 labs: delay/AsyncResult, retry+backoff+jitter, routing/chain/group/chord, acks_late crash experiment |

## 03. Ops

| Topic | Path | What it is |
|---|---|---|
| gRPC | [gRPC](03_Ops/gRPC) | Real `.proto` + generated stubs, 4 labs: unary, server-streaming, deadlines/retries, interceptor-auth |
| Docker / K8s / CI | [Docker_K8s_CI](03_Ops/Docker_K8s_CI) | 4 labs, real Docker: multi-stage build (measured size cut), nginx reverse proxy, Prometheus scrape+query, deployment health gate |
| Kubernetes | [Kubernetes](03_Ops/Kubernetes) | 5 labs on a real kind+Calico cluster: readiness-driven Service routing, ConfigMap hot-reload vs env staleness, OOMKill vs CPU throttling, NetworkPolicy default-deny/allow, Job backoffLimit |
| Terraform | [Terraform](03_Ops/Terraform) | 5 labs, no AWS account needed: `moved` blocks, `count` vs `for_each`, `create_before_destroy` ordering, real S3+DynamoDB backend (LocalStack), `terraform import` |
| Docker | [Docker](03_Ops/Docker) | 5 labs: build-secret leakage (`ARG` vs `--mount=type=secret`), non-root privilege enforcement, restart-policy semantics, read-only rootfs + tmpfs, BuildKit cache mounts |
| AWS | [AWS](03_Ops/AWS) | 5 labs, no AWS account needed (LocalStack): SQS DLQ redrive, SNS→SQS filter policies, DynamoDB conditional writes, Secrets Manager versioning, S3 event notifications |

## 04. Backend Projects (fleshed-out starters)

| Project | Path | Stack |
|---|---|---|
| FastAPI URL Shortener at Scale | [FastAPI_URL_Shortener](04_Backend_Projects/FastAPI_URL_Shortener) | FastAPI, Docker, docker-compose |
| Django Banking / Fintech | [Django_Banking_Fintech](04_Backend_Projects/Django_Banking_Fintech) | Django, Docker, docker-compose |
| FastAPI + OpenAI RAG Backend | [FastAPI_OpenAI_RAG_Backend](04_Backend_Projects/FastAPI_OpenAI_RAG_Backend) | FastAPI, OpenAI, Docker, docker-compose |

*(7 other starters under `Backend_Developer/03_Interview_AnyYear/03_Projects/` are still skeleton-stage — README + requirements.txt only, nothing to run yet. Left out of this hub until they're built out; not forgotten.)*

## 05. Agentic AI Projects

| Project | Path | What it is |
|---|---|---|
| Personal AI Assistant | [Personal_AI_Assistant](05_Agentic_Projects/Personal_AI_Assistant) | MCP-based personal assistant starter |
| RAG Document Q&A | [RAG_Document_QA](05_Agentic_Projects/RAG_Document_QA) | RAG-based document Q&A starter |
| Multi-Agent Code Review | [MultiAgent_Code_Review](05_Agentic_Projects/MultiAgent_Code_Review) | LangGraph + Claude subagents, GitHub webhook + Slack, MCP server |
| Production AI SaaS (triage agent) | [Production_AI_SaaS](05_Agentic_Projects/Production_AI_SaaS) | Evals, reliability testing, mutation testing, guardrails, cost/latency tracing — has its own [deploy build-plan](05_Agentic_Projects/Production_AI_SaaS/labs/README.md) |
| Wedding Transformation Agent | [Wedding_Transformation_Agent](05_Agentic_Projects/Wedding_Transformation_Agent) | 13-agent multi-agent fitness/planning system |
| Workspace Demo | [Workspace_Demo](05_Agentic_Projects/Workspace_Demo) | AI chat assistant demo |

## 06. DevOps Capstone

| Project | Path | What it is |
|---|---|---|
| RAG Backend (Terraform + K8s + CI) | [RAG_Backend_Terraform_K8s](06_DevOps_Capstone/RAG_Backend_Terraform_K8s) | The only hands-on capstone in the 21-phase DevOps track — Terraform, K8s manifests, CI template |

---

## Known gap, partially fixed

The top-level `DevOps/` track (21 phases) mostly has **no per-phase labs** —
theory + reference scripts only, unlike Backend_Developer's equivalent topics.
**Phase 5 (Docker), Phase 6 (Kubernetes), Phase 7 (AWS), and Phase 8
(Terraform) are now fixed** (labs above). The other 16 phases (Linux, Bash,
Networking, Ansible, CI/CD, Monitoring, Logging, etc.) still have no
hands-on labs beyond the one capstone. If you want another phase built out,
say which one.

## How to keep this in sync

New labs/projects built later (anywhere in the repo) won't auto-appear here —
add a new symlink (`ln -s ../../<relative path to target> PRACTICE_HUB/<section>/<Name>`)
and a row in the matching table above.
