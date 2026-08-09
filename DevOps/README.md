# 🛠️ DevOps Engineer Track

> Standalone DevOps curriculum — Linux → Bash → Networking → Git → Docker → Kubernetes → AWS → Terraform → Ansible → CI/CD → Monitoring → Logging → Web Servers → Security → Databases → Messaging → Caching → System Design → Observability → Best Practices → Projects.

**Why this exists:** you already have 4.4 years of Python backend experience + 1 year Agentic AI (see [`../Backend_Developer/`](../Backend_Developer/)). This track is not "DevOps in isolation" — every phase should be tied back to *deploying and operating the kind of backend services you already build*. That combo (Backend + DevOps) is the strongest positioning for the roles you're targeting.

Related, narrower DevOps content already exists at [`../Backend_Developer/01_Year3-4_Mid/04_DevOps/`](../Backend_Developer/01_Year3-4_Mid/04_DevOps/) (Docker, Nginx, GitHub Actions, AWS EC2/S3/RDS, Prometheus/Grafana, Kubernetes/Helm, Terraform, ELK/Loki, deployment strategies, GitOps + ArgoCD/Flux/Kustomize in full depth, chaos engineering, SRE, eBPF, OpenTelemetry) — that folder is backend-deployment-focused; this track is the full infra-engineer curriculum including Linux/Bash/Networking foundations it assumes you already have. Cross-links are noted inline where the two overlap so you don't relearn the same thing twice.

**Serverless (AWS Lambda / API Gateway / EventBridge)** is deliberately not a phase here either — Phase 7 (Cloud/AWS) covers the always-on compute model (EC2, ECS/EKS, Fargate). The event-driven serverless model has a full lesson at [`../Backend_Developer/01_Year3-4_Mid/04_DevOps/22_aws_managed_services.md`](../Backend_Developer/01_Year3-4_Mid/04_DevOps/22_aws_managed_services.md) (Lambda, API Gateway, EventBridge, CloudWatch, Secrets Manager, ECS vs EKS). Many 2026 India JDs list Lambda explicitly — read it after Phase 7.

**Service mesh (Istio/Linkerd)** is deliberately not a phase here — a full lesson already exists at [`../Backend_Developer/01_Year3-4_Mid/05_Microservices/06_service_mesh_istio_linkerd.md`](../Backend_Developer/01_Year3-4_Mid/05_Microservices/06_service_mesh_istio_linkerd.md); read it after Phase 6 (Kubernetes) if your target roles mention Istio.

**Operating what you build with Agentic AI** — deploying/observing LLM and RAG services (cost/token monitoring, guardrails, LLM-specific observability, prompt/model versioning) isn't covered in this DevOps track at all; it's a separate, already-built phase at [`../Agentic_AI/Level8_Production_LLMOps/`](../Agentic_AI/Level8_Production_LLMOps/). Given your background is Backend + DevOps + Agentic AI combined, that phase is arguably your strongest differentiator over other "Backend + DevOps" candidates — don't skip cross-referencing it once you're through Phase 19 (Observability) here.

## 📂 Structure & Recommended Order

| # | Phase | Folder | Focus |
|---|-------|--------|-------|
| 1 | Linux (Foundation) | [`01_Linux/`](01_Linux/) | Distros, FHS, permissions, users/groups, essential commands, compression, process/disk/network mgmt, services |
| 2 | Bash Scripting | [`02_Bash_Scripting/`](02_Bash_Scripting/) | Variables, loops, functions, arrays, cron, log parsing, backup automation |
| 3 | Networking | [`03_Networking/`](03_Networking/) | OSI, TCP/IP, subnetting/CIDR, protocols, reverse proxy/CDN/load balancer |
| 4 | Git | [`04_Git/`](04_Git/) | Branching, rebase, cherry-pick, stash, Git Flow, conflict resolution |
| 5 | Docker | [`05_Docker/`](05_Docker/) | Images/containers, Dockerfile, Compose, storage, networking, registries |
| 6 | Kubernetes | [`06_Kubernetes/`](06_Kubernetes/) | Architecture, objects, services, storage, config, scaling, security, Helm, cluster autoscaling/Karpenter |
| 7 | Cloud (AWS) | [`07_Cloud_AWS/`](07_Cloud_AWS/) | IAM, EC2, S3/EBS/EFS, RDS/DynamoDB, VPC, Route 53, ALB/NLB, ECS/EKS, CloudWatch, SNS/SQS, Secrets Manager |
| 8 | Terraform (IaC) | [`08_Terraform/`](08_Terraform/) | Providers, state, modules, backends, workspaces |
| 9 | Ansible | [`09_Ansible/`](09_Ansible/) | Inventory, playbooks, roles, vault, Galaxy |
| 10 | CI/CD | [`10_CICD/`](10_CICD/) | Jenkins pipelines, GitHub Actions workflows/matrix/secrets/runners |
| 11 | Monitoring | [`11_Monitoring/`](11_Monitoring/) | Prometheus, PromQL, Grafana, Alertmanager |
| 12 | Logging | [`12_Logging/`](12_Logging/) | ELK Stack, Loki, Fluentd/Fluent Bit |
| 13 | Web Servers | [`13_Web_Servers/`](13_Web_Servers/) | Nginx (reverse proxy, LB, SSL, caching, rate limiting), Apache basics |
| 14 | Security | [`14_Security/`](14_Security/) | SSH hardening, TLS, secrets mgmt, OWASP Top 10, Docker/K8s security, IAM best practices, vuln/image scanning |
| 15 | Databases | [`15_Databases/`](15_Databases/) | SQL (MySQL/PostgreSQL) + NoSQL (MongoDB/Redis) ops for DevOps |
| 16 | Messaging Systems | [`16_Messaging_Systems/`](16_Messaging_Systems/) | RabbitMQ, Kafka, Redis Streams, SQS/SNS |
| 17 | Caching | [`17_Caching/`](17_Caching/) | Redis, Memcached, invalidation strategies, distributed cache |
| 18 | System Design | [`18_System_Design/`](18_System_Design/) | Monolith vs microservices, API gateway, CAP theorem, event-driven architecture, scaling |
| 19 | Observability | [`19_Observability/`](19_Observability/) | Metrics/logs/traces, OpenTelemetry, Jaeger, Zipkin |
| 20 | DevOps Best Practices | [`20_Best_Practices/`](20_Best_Practices/) | Blue-green, canary, rolling updates, GitOps, feature flags, zero-downtime, DR, incident response, cost optimization |
| 21 | Projects | [`21_Projects/`](21_Projects/) | 10 hands-on projects tying every phase together |

## 🧭 Recommended learning order

Linux → Networking → Git → Bash Scripting → Docker → AWS Fundamentals → Terraform → Kubernetes → CI/CD (GitHub Actions/Jenkins) → Monitoring & Logging → Security → System Design → Advanced Kubernetes & GitOps.

## How to use each phase folder

Every phase folder contains one or more numbered `.md` files: quick-concept definitions first, then commands/config with real examples, then a **Senior Tip** or **Interview Angle** section tying it back to production/backend-deployment reality. Read in file-number order within a folder.

Phases 1–20 also have a `practical/` subfolder — one hands-on lab file with 3-4 escalating exercises (basic → multi-step → realistic production/debugging scenario) and collapsible solutions. Do the lab right after reading that phase's lesson files, don't just read the solutions. Phase 21 (`21_Projects/`) is the capstone — it's the practical for the whole track, tying multiple phases together.

**Study loop per phase:** read the lesson file(s) → attempt every lab in `practical/` without peeking → check the Self-Check Checklist at the bottom of the lab file → only then open the `<details>` solution blocks to compare.
