# 🚀 DevOps Track — Capstone Projects
**DevOps Track · Phase 21: Projects**

> These 10 projects are a **single progressive capstone**, not 10 disconnected exercises. Each one builds on artifacts from the previous: the Dockerfile from Project 1 is what Project 2's pipeline builds, what Project 3 deploys to EC2, what Project 5 deploys to Kubernetes, what Project 8 wraps in a Helm chart, what Project 9 blue-green deploys, and what Project 10 turns into a full multi-service production architecture. Do them in order. Skipping ahead means re-doing setup work later projects assume already exists.

## How to use this phase

Each project brief below gives: **Goal**, **Stack/tools used** (mapped to specific phase folders in this track so you know what to review before starting), **Steps**, and **Definition of Done**. Treat "Definition of Done" as a checklist — a project isn't finished until every line is true, not just "it ran once on my machine."

**Closing note (read before starting Project 1):** this repo already has real, non-trivial FastAPI/Django starter applications at [`Backend_Developer/03_Interview_AnyYear/03_Projects/`](../../Backend_Developer/03_Interview_AnyYear/03_Projects/) — e.g. `05_Django_Banking_Fintech_starter`, `08_FastAPI_OpenAI_RAG_Backend_starter`, `06_Django_HR_Payroll_starter`. Use ONE of those as the app you deploy across all 10 projects instead of building a throwaway "hello world" Flask app. A banking/fintech Django app with real models, auth, and a Postgres dependency gives you actual production concerns to solve (migrations, secrets, background workers, connection pooling) — a toy app doesn't, and your resume/interview story is far stronger when you can say "I containerized and deployed a real multi-model Django app with Postgres and Redis" rather than "I deployed hello-world."

---

## Project 1 — Dockerize a Django Application

**Goal:** take a real Django app and produce a production-grade container image — not just something that runs, but something you'd trust in production (multi-stage build, non-root user, small image, proper static file handling).

**Stack/tools used:** [`05_Docker/`](../05_Docker/) (Dockerfile, multi-stage builds, `.dockerignore`), [`15_Databases/`](../15_Databases/) (Postgres container for local dev), Docker Compose.

**Steps:**
1. Pick a real starter app — recommended: `05_Django_Banking_Fintech_starter` from the Interview Projects folder.
2. Write a multi-stage `Dockerfile`: builder stage installs deps + collects static files, final stage copies only the runtime artifacts (no compilers/build tools in the final image).
3. Run as a non-root user (`USER appuser`), set `WORKDIR`, use `gunicorn`/`uvicorn` as the process manager, not `runserver`.
4. Add a `.dockerignore` (exclude `.git`, `__pycache__`, `.env`, `node_modules`, test artifacts).
5. Write a `docker-compose.yml` wiring the app container to a Postgres container and a Redis container, with named volumes and a health-checked `depends_on`.
6. Externalize all config via environment variables (`DATABASE_URL`, `SECRET_KEY`, `DEBUG`) — never bake secrets into the image.
7. Add a `HEALTHCHECK` instruction (hits `/healthz` or Django's own health endpoint).
8. Verify: `docker build`, `docker compose up`, app reachable, migrations run, static files served correctly.

**Definition of Done:**
- [ ] Image builds in under 2 minutes on a clean cache
- [ ] Final image size is reasonable (no build toolchain baked in — check with `docker images`)
- [ ] Container runs as non-root
- [ ] `docker compose up` gives a fully working app + DB + cache with one command
- [ ] No secret is hardcoded in the Dockerfile or image layers (`docker history` shows none)

---

## Project 2 — Set Up CI/CD with GitHub Actions

**Goal:** every push to `main` automatically lints, tests, builds the Project 1 Docker image, and pushes it to a container registry — no manual steps.

**Stack/tools used:** [`10_CICD/`](../10_CICD/), the Dockerfile from **Project 1**, GitHub Container Registry (GHCR) or Docker Hub.

**Steps:**
1. Write `.github/workflows/ci.yml`: on every PR, run `flake8`/`ruff` lint, run `pytest` against a Postgres service container spun up in the workflow itself.
2. Add a separate job (or a second workflow) triggered on merge to `main`: builds the Project 1 Dockerfile and tags the image with the Git SHA + `latest`.
3. Push the built image to GHCR using `docker/build-push-action`, authenticated via `GITHUB_TOKEN` (no long-lived credentials).
4. Use GitHub Actions **secrets** for anything sensitive (`DATABASE_URL` for test DB if needed) — never plaintext in the workflow file.
5. Add a build cache (`docker/build-push-action`'s `cache-from`/`cache-to` with GHA cache) so repeat builds are fast.
6. Add a status badge to the app's README reflecting the current build status.
7. Make the test job a required check before merge (branch protection rule).

**Definition of Done:**
- [ ] A PR that fails lint or tests cannot be merged (branch protection enforced)
- [ ] A merge to `main` automatically produces a new tagged image in the registry within minutes
- [ ] No secret appears in workflow logs
- [ ] Build uses caching (second run is measurably faster than the first)

---

## Project 3 — Deploy Django to AWS EC2

**Goal:** run the Project 1 image (now auto-built by Project 2's pipeline) on a real EC2 instance, reachable over the internet with a domain and HTTPS.

**Stack/tools used:** [`07_Cloud_AWS/`](../07_Cloud_AWS/) (EC2, Security Groups, Elastic IP, RDS), [`13_Web_Servers/`](../13_Web_Servers/) (Nginx as reverse proxy + TLS termination), the image from **Project 2**.

**Steps:**
1. Provision an EC2 instance (manually via console/CLI for this project — Terraform comes in Project 4).
2. Provision an RDS Postgres instance (or start with Postgres on the same box, then migrate to RDS to feel the difference).
3. Configure a Security Group: only 22 (SSH, locked to your IP), 80, 443 open.
4. Install Docker on the instance, pull the image built by the Project 2 pipeline, run it with the production `.env` (via SSM Parameter Store or a `.env` file with `chmod 600`, never committed).
5. Install Nginx on the host (or run it as a sibling container) as a reverse proxy in front of the app container — terminate TLS here.
6. Point a domain (or subdomain) at the instance's Elastic IP, get a cert with Let's Encrypt/Certbot.
7. Set up the app as a systemd-managed Docker container (`Restart=always`) or a `docker-compose.yml` run via a systemd unit, so it survives reboots.
8. Verify zero-downtime restart behavior isn't expected yet at this stage (that's Project 9) — just confirm it comes back up after `sudo reboot`.

**Definition of Done:**
- [ ] App reachable over HTTPS at a real domain
- [ ] SSH restricted to your IP only, all other unnecessary ports closed
- [ ] Secrets are not committed to Git and not visible in `docker inspect`/process list
- [ ] Instance survives a reboot with the app auto-starting
- [ ] Database is RDS, not co-located on the app instance

---

## Project 4 — Create Infrastructure with Terraform

**Goal:** replace every manual click from Project 3 with declarative Terraform — the whole EC2 + RDS + networking stack becomes reproducible from code.

**Stack/tools used:** [`08_Terraform/`](../08_Terraform/), reproducing exactly what Project 3 built by hand.

**Steps:**
1. Write Terraform for the VPC (or use the default VPC intentionally, documented as a choice) — subnets, route tables, internet gateway.
2. Define the Security Group, EC2 instance, and Elastic IP as resources.
3. Define the RDS instance (engine, size, storage, backup retention) as a resource, with the master password sourced from a variable marked `sensitive`, never hardcoded.
4. Use a remote backend for state — S3 bucket + DynamoDB table for state locking, not local `.tfstate` (which can't be shared or safely used by CI).
5. Parameterize environment-specific values (`instance_type`, `db_instance_class`) via `.tfvars`, with separate `dev.tfvars` and `prod.tfvars`.
6. Structure as reusable modules (`modules/ec2`, `modules/rds`, `modules/networking`) even if you only use each once — this is what Project 5 will reuse.
7. Run `terraform plan` and review every resource before `terraform apply`. Destroy the manual Project 3 resources and recreate them entirely from Terraform to prove it's truly reproducible.
8. Add `terraform fmt` + `terraform validate` as a CI check (extend Project 2's pipeline).

**Definition of Done:**
- [ ] `terraform destroy` then `terraform apply` fully recreates the Project 3 environment with no manual steps
- [ ] State is stored remotely with locking (no local `.tfstate` in Git)
- [ ] No secret is hardcoded in `.tf` files (verified by `git grep` for passwords/keys before commit)
- [ ] Infrastructure is modularized, not one giant `main.tf`

---

## Project 5 — Deploy to Kubernetes (EKS or Minikube)

**Goal:** move off single-instance EC2 onto Kubernetes — replicas, self-healing, rolling updates, and (if using EKS) reuse Project 4's Terraform for the cluster itself.

**Stack/tools used:** [`06_Kubernetes/`](../06_Kubernetes/), [`08_Terraform/`](../08_Terraform/) (EKS module, reusing Project 4's networking module), [`18_System_Design/`](../18_System_Design/) (service discovery, load balancing concepts now made concrete).

**Steps:**
1. Choose EKS (real cloud, costs money, closer to a real job) or Minikube (free, local, good enough to learn the object model) — recommended: Minikube first to learn free, then EKS once comfortable, using Terraform's EKS module extending Project 4's VPC module.
2. Write a `Deployment` manifest for the app (image from Project 2's registry), a `Service` (ClusterIP), and an `Ingress` (or `LoadBalancer` Service on EKS) to expose it.
3. Configure `readinessProbe` and `livenessProbe` against the app's health endpoint — this is the gate for everything in later projects.
4. Externalize config via `ConfigMap` (non-sensitive) and `Secret` (DB credentials, `SECRET_KEY`) — never inline in the Deployment spec.
5. Set `resources.requests` and `resources.limits` for CPU/memory based on observed usage, not guesses.
6. Deploy Postgres via a managed service (RDS, reusing Project 4's module) rather than in-cluster — stateful workloads in K8s are a deeper topic than this project scope.
7. Confirm self-healing: kill a pod manually (`kubectl delete pod`), watch Kubernetes recreate it automatically.
8. Confirm a rolling update works: change the image tag, `kubectl apply`, watch pods replace incrementally with zero dropped requests (curl in a loop during the rollout).

**Definition of Done:**
- [ ] `kubectl get pods` shows N healthy replicas, self-heals when one is killed
- [ ] Rolling update replaces all pods with zero failed requests during the rollout (verified by a curl loop, not assumed)
- [ ] No secret is stored in a ConfigMap or plaintext manifest committed to Git
- [ ] Ingress/LoadBalancer routes external traffic to the Service correctly

---

## Project 6 — Add Prometheus and Grafana Monitoring

**Goal:** you can no longer answer "is it healthy" by SSHing in and looking — you have dashboards and alerts.

**Stack/tools used:** [`11_Monitoring/`](../11_Monitoring/), [`19_Observability/`](../19_Observability/), the K8s cluster from **Project 5**.

**Steps:**
1. Install `kube-prometheus-stack` via Helm (this previews Project 8's Helm skill) into the cluster from Project 5.
2. Expose app-level metrics from Django (request count, latency histogram, error rate) using `django-prometheus`, scraped by Prometheus via a `ServiceMonitor`.
3. Build a Grafana dashboard: request rate, error rate, p50/p95/p99 latency, pod CPU/memory, pod restart count.
4. Write Alertmanager rules: alert if error rate > 5% for 5 minutes, alert if p99 latency > 1s for 5 minutes, alert if any pod is in `CrashLoopBackOff`.
5. Route alerts to a real notification channel (Slack webhook, email) — not just "visible in a UI nobody watches."
6. Load-test the app (`locust` or `hey`) and watch the dashboard react in real time; confirm an alert actually fires when you push it past the threshold.

**Definition of Done:**
- [ ] Grafana dashboard shows live request rate, error rate, and latency percentiles for the app
- [ ] At least one alert rule has been proven to fire (tested under induced load/failure, not just written and assumed correct)
- [ ] Alerts reach a real channel, not just the Alertmanager UI

---

## Project 7 — Configure Centralized Logging with ELK or Loki

**Goal:** logs from every pod are aggregated, searchable, and correlated back to requests — no more `kubectl logs` pod-by-pod archaeology.

**Stack/tools used:** [`12_Logging/`](../12_Logging/), [`19_Observability/`](../19_Observability/) (structured logging + trace_id correlation), the K8s cluster from **Project 5**.

**Steps:**
1. Choose Loki (lighter, pairs naturally with the Grafana from Project 6) or the ELK stack (heavier, more powerful full-text search) — recommended: Loki, since it shares Grafana with your Project 6 dashboards.
2. Deploy Loki + Promtail (or Fluent Bit) via Helm into the cluster; Promtail/Fluent Bit runs as a DaemonSet, scraping every pod's stdout/stderr.
3. Convert the Django app's logging to structured JSON (via `python-json-logger` or similar) with a consistent field set: `timestamp`, `level`, `service`, `trace_id`, `message`.
4. Add Loki as a Grafana data source, alongside the Prometheus data source from Project 6 — one Grafana instance for metrics AND logs.
5. Write a LogQL query that filters to `level=ERROR` for the app, and one that filters logs by a specific `trace_id` (prep for Project 6's OTel-style correlation once you add tracing).
6. Set log retention (e.g., 14 days for INFO, 90 days for ERROR) to control cost — don't keep everything forever by default.

**Definition of Done:**
- [ ] Logs from every pod are queryable in one place (Grafana + Loki, or Kibana)
- [ ] Logs are structured JSON with a consistent field schema, not raw text
- [ ] You can filter to errors for a specific service/pod in under 10 seconds without SSHing anywhere
- [ ] Retention policy is explicitly configured, not left at default/unlimited

---

## Project 8 — Deploy Using Helm

**Goal:** package the raw manifests from Project 5 into a proper Helm chart — versioned, parameterized, and reusable across environments (dev/staging/prod) with one command each.

**Stack/tools used:** [`06_Kubernetes/`](../06_Kubernetes/) (Helm section), reusing every manifest from **Project 5**, **Project 6**, and **Project 7**.

**Steps:**
1. Run `helm create orders-app` to scaffold the chart structure, then replace the generated templates with the actual Deployment/Service/Ingress/ConfigMap/Secret from Project 5.
2. Move every hardcoded value (replica count, image tag, resource limits, domain name) into `values.yaml`, templated with `{{ .Values.xxx }}`.
3. Create `values-dev.yaml`, `values-staging.yaml`, `values-prod.yaml` overriding only what differs (replica count, resource limits, domain).
4. Add the Project 6 ServiceMonitor and Project 7 log-label annotations as optional sub-templates gated by `.Values.monitoring.enabled`.
5. Version the chart (`Chart.yaml` `version:` field), and bump it on every meaningful change — this is what makes `helm rollback` possible later.
6. Deploy to all three environments with one command each: `helm upgrade --install orders-app ./chart -f values-prod.yaml`.
7. Practice `helm rollback orders-app 1` and confirm it actually reverts cleanly.

**Definition of Done:**
- [ ] `helm install`/`upgrade` deploys correctly to dev, staging, and prod using the same chart with only values overridden
- [ ] `helm rollback` to a previous revision has been tested and works
- [ ] No environment-specific value is hardcoded inside a template (only in the relevant `values-*.yaml`)
- [ ] `helm lint` passes clean

---

## Project 9 — Implement Blue-Green Deployment

**Goal:** put the Phase 20 theory into practice — deploy a new version to a fully separate "green" environment and cut traffic over instantly, with an instant rollback path.

**Stack/tools used:** [`20_Best_Practices/`](../20_Best_Practices/) (blue-green + zero-downtime checklist), the Helm chart from **Project 8**, the K8s cluster from **Project 5**.

**Steps:**
1. Deploy two full releases of the Helm chart from Project 8 with distinct labels: `orders-app-blue` and `orders-app-green`, each with its own Deployment but pointing at the same database.
2. Put a single Service (or Ingress) in front, selecting pods by a shared label (`app: orders-app`) plus a `version` label that you control (`version: blue`).
3. Deploy the new version to green (`version: green`) while blue keeps serving 100% of traffic — verify green passes health checks and smoke tests internally (port-forward, don't expose yet).
4. Cut over by updating the Service selector (or Ingress backend) from `version: blue` to `version: green` — traffic switches atomically.
5. Watch Project 6's dashboards for 10-15 minutes post-cutover.
6. Practice the rollback: switch the selector back to `version: blue` and confirm it's instant, with blue's pods still warm (don't tear blue down immediately after a cutover — that's what makes rollback instant).
7. Only after confidence in green, scale blue down to 0 replicas (keep the Deployment around for the next cycle, where blue becomes the new "idle" target).

**Definition of Done:**
- [ ] Cutover from blue to green causes zero failed requests (verified with a curl loop spanning the cutover moment)
- [ ] Rollback to the previous color takes under 1 minute and has been actually tested, not just planned
- [ ] Database schema compatibility between blue and green was explicitly considered (expand/contract pattern from Phase 20 if the release included a schema change)

---

## Project 10 — Production-Ready Multi-Service Architecture

**Goal:** the capstone — assemble everything into one architecture with PostgreSQL, Redis, RabbitMQ, and Nginx, each doing its real production job, all deployed and observed using everything built in Projects 1-9.

**Stack/tools used:** [`15_Databases/`](../15_Databases/) (Postgres), [`17_Caching/`](../17_Caching/) (Redis), [`16_Messaging_Systems/`](../16_Messaging_Systems/) (RabbitMQ), [`13_Web_Servers/`](../13_Web_Servers/) (Nginx), [`18_System_Design/`](../18_System_Design/) (tying the architecture together), plus the full CI/CD, Terraform, Kubernetes, Helm, monitoring, logging, and blue-green tooling from every prior project.

**Architecture:**

```
                    ┌──────────┐
   Internet ──────► │  Nginx   │  (reverse proxy, TLS termination, rate limiting)
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │ Django/  │  (web tier — horizontally scaled, K8s Deployment)
                    │ FastAPI  │
                    └──┬────┬──┘
                       │    │
              ┌────────┘    └────────┐
              ▼                       ▼
        ┌──────────┐           ┌──────────┐
        │  Redis   │           │ RabbitMQ │──► Celery workers (async tasks:
        │ (cache + │           │ (message │     emails, reports, webhooks)
        │ sessions)│           │  broker) │
        └──────────┘           └──────────┘
              │
              ▼
        ┌──────────┐
        │ Postgres │  (primary + read replica, RDS Multi-AZ)
        └──────────┘

   All services: Prometheus metrics + Loki logs (Projects 6-7)
   Deployment: Helm chart (Project 8), blue-green (Project 9)
   Infra: Terraform (Project 4), CI/CD (Project 2)
```

**Steps:**
1. Add Redis to the architecture for two distinct purposes: Django session/cache backend AND Celery result backend — deploy via a managed service (ElastiCache) or an in-cluster StatefulSet, documented as a deliberate choice.
2. Add RabbitMQ as the Celery broker; move at least one real slow operation (e.g., sending confirmation emails, generating a report) from synchronous request handling into an async Celery task.
3. Add Nginx in front of the whole stack (if not already handled by the K8s Ingress) for TLS termination, gzip, and basic rate limiting — document the difference between this and the Ingress controller's job.
4. Extend the Helm chart (Project 8) with sub-charts or additional templates for Redis, RabbitMQ, and Celery worker Deployments (separate from the web Deployment, scaled independently).
5. Extend Terraform (Project 4) to provision ElastiCache and Amazon MQ (or self-managed RabbitMQ) alongside the existing RDS/EKS resources.
6. Extend monitoring (Project 6) with Redis and RabbitMQ exporters — dashboard panels for cache hit rate, queue depth, and consumer lag (queue depth is one of the most important signals in an event-driven system, per Phase 18).
7. Load-test the full stack and confirm: web tier autoscales (HPA) under load, Celery workers autoscale independently based on queue depth (KEDA, or a simple queue-depth-based HPA), Redis cache hit rate stays healthy, and blue-green (Project 9) still works cleanly with this many moving parts.
8. Write a one-page architecture doc (README in the project itself) explaining every component's job — this doc is your interview cheat sheet.

**Definition of Done:**
- [ ] All four services (Postgres, Redis, RabbitMQ, Nginx) are deployed, each doing a distinct, real job, not just present for show
- [ ] At least one real workflow is fully async via Celery/RabbitMQ (not just an example task)
- [ ] Full observability: metrics + logs for every component, not just the web tier
- [ ] Blue-green deployment (Project 9) still works correctly with the full multi-service stack
- [ ] Everything is provisioned via Terraform + deployed via the Helm chart + CI/CD pipeline — zero manual `kubectl apply`/console clicks for a fresh environment stand-up

---

## Closing Note — Don't Build Throwaway Apps

Every project above assumes you're deploying a **real application with real complexity** — models, auth, background jobs, a database schema that actually needs migrations — not a "hello world" Flask/Django stub. This repo already has exactly that at [`Backend_Developer/03_Interview_AnyYear/03_Projects/`](../../Backend_Developer/03_Interview_AnyYear/03_Projects/):

- **`05_Django_Banking_Fintech_starter`** — real models, auth, transactions; good fit for Projects 1-9 (relational data, migrations to worry about in blue-green)
- **`08_FastAPI_OpenAI_RAG_Backend_starter`** — has an external API dependency (OpenAI) and a vector store, good fit for Project 10's multi-service architecture (adds a realistic "external dependency can fail" dimension to your observability/incident-response practice)
- **`06_Django_HR_Payroll_starter`** or **`07_Django_Food_Delivery_starter`** — also solid, pick whichever domain you find easiest to reason about under deployment pressure

Pick ONE app and carry it through all 10 projects. By Project 10, you'll have a genuine "I deployed and operated a production-grade multi-service system" story for interviews — with real architecture decisions you made and can defend, not a tutorial you followed.

---

## Related

- [`../18_System_Design/01_system_design_fundamentals.md`](../18_System_Design/01_system_design_fundamentals.md) — the vocabulary behind Project 10's architecture
- [`../19_Observability/01_metrics_logs_traces_opentelemetry.md`](../19_Observability/01_metrics_logs_traces_opentelemetry.md) — Projects 6-7's foundation
- [`../20_Best_Practices/01_deployment_dr_incident_cost.md`](../20_Best_Practices/01_deployment_dr_incident_cost.md) — Project 9's foundation, plus DR/incident-response practice once Project 10 is live
- [`../README.md`](../README.md) — full DevOps track index
