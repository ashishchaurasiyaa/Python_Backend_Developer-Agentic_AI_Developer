# Capstone — RAG Backend, Containerized and Deployed Locally

Real artifacts for Projects 1, 2, 4, and 5 of [`../README.md`](../README.md)'s
progressive capstone — built against the one genuinely real starter app in
this repo, [`08_FastAPI_OpenAI_RAG_Backend_starter`](../../../Backend_Developer/03_Interview_AnyYear/03_Projects/08_FastAPI_OpenAI_RAG_Backend_starter/), per that project brief's own closing note.

## Status — verified, not assumed

| Project | Artifact | Status |
|---|---|---|
| **1 — Dockerize** | [`Dockerfile`](../../../Backend_Developer/03_Interview_AnyYear/03_Projects/08_FastAPI_OpenAI_RAG_Backend_starter/Dockerfile), [`docker-compose.yml`](../../../Backend_Developer/03_Interview_AnyYear/03_Projects/08_FastAPI_OpenAI_RAG_Backend_starter/docker-compose.yml), [`.dockerignore`](../../../Backend_Developer/03_Interview_AnyYear/03_Projects/08_FastAPI_OpenAI_RAG_Backend_starter/.dockerignore) | ✅ **Fully verified, live.** `docker compose up -d --build` brings up app+Postgres+Redis together, all three report `healthy`. `curl localhost:8001/health` returns real JSON, `/docs` returns 200, all 6 app routes present in `/openapi.json`. Confirmed non-root (`docker exec ... whoami` → `appuser`), confirmed no baked secrets (`docker history`), confirmed the container survives a restart and comes back healthy (`docker restart` + re-curl). Image: 833MB.<br><br>**Two bare image tags turned out to have broken arm64 manifests** on this host — `pgvector/pgvector:pg16` and `redis:7` both failed with `exec format error` even freshly pulled on a clean Docker VM, confirmed via a bare `docker run <tag> --version` on each (unrelated to this compose file). Swapped to `pgvector/pgvector:pg16-trixie` and `redis:7-alpine`, both confirmed working — comment left in the compose file explaining why, so a future you doesn't waste time re-diagnosing it.<br><br>**Also found a host port collision**: 8000 was already bound by an unrelated local `php` process — remapped to `8001:8000` rather than touching whatever that other process was doing. |
| **2 — CI/CD** | [`ci_template/ci.yml`](ci_template/ci.yml) | ⬜ **Written, not active** — deliberately placed outside `.github/workflows/` so it can't accidentally start firing on pushes to this study repo. Copy it to the real app repo's `.github/workflows/ci.yml` to activate. |
| **4 — Terraform** | [`terraform/`](terraform/) | ⬜ **Written, not applied** — modularized (networking/ec2/rds), remote S3+DynamoDB state backend configured, `db_password` sourced from a `sensitive` variable with no default. Brace-balance checked; **not run through `terraform validate`** — this machine has no `terraform` binary installed. Applying needs a real AWS account and will cost money — that's a deliberate stop point, not an oversight. |
| **5 — Kubernetes** | [`k8s/`](k8s/) | ⬜ **Written, not applied** — Deployment (3 replicas, zero-downtime rolling update config), Service, Ingress, ConfigMap, Secret template, HPA. All 6 YAML files parsed successfully with Python's `yaml` module; **not run through `kubectl apply --dry-run`** — no `kubectl` and no local cluster available in this environment. |

**The honest summary:** Project 1 is now genuinely done — built, run, curled,
restarted, all checked live, not assumed. Projects 2/4/5 are written
correctly but need your own GitHub repo / AWS account to actually activate —
that's a real boundary, not a shortcut.

## What changed vs. the original audit finding

The repo-wide audit that led to this work found: *"No Dockerfile, no
Terraform, no CI workflow, no deployment artifact exists anywhere in
[`DevOps/`]."* That's no longer true — real, tested-where-testable artifacts
now exist for 4 of the 10 capstone projects. Projects 3 (manual EC2, superseded
by Project 4's Terraform anyway), 6–9 (monitoring/logging/Helm/blue-green),
and 10 (multi-service) remain as written specs only.

## Next steps, in order

1. `minikube start` (free, local) and actually `kubectl apply -f k8s/` — see
   [`k8s/README.md`](k8s/README.md) for the exact commands and what to fill in first.
2. Get an AWS account if you don't have one, create the S3 bucket + DynamoDB
   table `terraform/main.tf`'s backend block expects, then `terraform plan`
   against `environments/dev.tfvars` — read the plan output before ever
   running `apply` against real infrastructure.
3. Once the app has a real GitHub repo of its own, copy `ci_template/ci.yml`
   into `.github/workflows/` there.

## Reproduce Project 1's verification yourself

```bash
cd ../../../Backend_Developer/03_Interview_AnyYear/03_Projects/08_FastAPI_OpenAI_RAG_Backend_starter
docker compose up -d --build
curl http://localhost:8001/health          # {"status":"ok",...}
curl http://localhost:8001/docs            # 200, Swagger UI
docker compose down                        # when done
```
