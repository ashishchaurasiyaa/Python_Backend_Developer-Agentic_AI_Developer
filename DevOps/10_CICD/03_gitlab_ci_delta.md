# CI/CD — GitLab CI (Delta Lesson)
**DevOps Track · Phase 10: CI/CD**

> **Delta lesson** — deliberately short. Read [`02_github_actions.md`](02_github_actions.md) first; this file only covers what's DIFFERENT in GitLab CI, not CI/CD fundamentals again. If you know GHA, you already know ~80% of GitLab CI — this is the other 20%.

## Quick Concepts (GitLab ↔ GHA Mapping)

- **`.gitlab-ci.yml`** = ONE file at repo root (vs GHA's many files in `.github/workflows/`)
- **Pipeline** = one full run of `.gitlab-ci.yml` ≈ a GHA workflow run
- **Stage** = a named phase (`lint`, `test`, `deploy`); all jobs in a stage run in parallel, stages run sequentially — GHA has no direct equivalent (you'd fake it with `needs` chains)
- **Job** = a named block with a `script:` ≈ a GHA job, but steps are plain shell lines, not marketplace Actions
- **Runner** = the machine executing jobs ≈ GHA runner, but with pluggable **executors** (shell/docker/kubernetes)
- **`rules:`** = per-job conditional logic ≈ GHA's `if:` + `on:` combined
- **`needs:`** = DAG edges that let a job start before its whole stage finishes ≈ GHA `needs`, but here it's an OPTIMIZATION on top of stages
- **`include:`** = pull YAML from other files/repos/templates ≈ reusable workflows, but textual/merge-based
- **Environment** = named deploy target with URL, history, and rollback UI ≈ GHA environments, but richer (review apps, stop actions)
- **`CI_*` variables** = predefined vars (`CI_COMMIT_SHA`, `CI_REGISTRY_IMAGE`) ≈ `github.*` context

---

## Why This Matters

```
GitLab is the second-most-common CI you'll meet — the default in
companies that self-host their source control (enterprises, EU
companies with data-residency rules, telecoms, banks).

Interviewers at those companies don't expect years of GitLab —
they expect you to MAP your Jenkins/GHA knowledge onto it in days.
That mapping is exactly what this file is: same concepts, different
YAML keys, plus the handful of things GitLab genuinely does better
(built-in registry, review apps, includes).
```

---

## Anatomy Side-by-Side

| Concern | GitHub Actions | GitLab CI |
|---|---|---|
| File location | `.github/workflows/*.yml` (many files) | `.gitlab-ci.yml` (one file at repo root) |
| Unit of execution | workflow → jobs → steps | pipeline → stages → jobs → `script:` lines |
| Ordering | jobs parallel by default; `needs` for order | jobs grouped into sequential `stages`; parallel within a stage |
| Trigger config | `on: push/pull_request/...` per workflow | `workflow: rules:` (pipeline-level) + `rules:` (job-level) |
| Conditionals | `if: github.ref == ...` | `rules: - if: '$CI_COMMIT_BRANCH == "main"'` |
| Reuse | marketplace Actions, reusable workflows, composite actions | `include:`, `extends:`, YAML anchors, GitLab-maintained templates |
| Container per job | `container:` (optional, VM is default) | `image:` (docker executor — container IS the default) |
| Sidecars (DB for tests) | `services:` | `services:` (same idea, e.g. `postgres:16`) |
| Secrets | repo/org/environment secrets, `${{ secrets.X }}` | CI/CD variables (masked/protected flags), external Vault/OIDC |
| Registry | GHCR (separate product, `docker/login-action`) | built-in per-project registry, `$CI_REGISTRY_IMAGE`, auto-auth |
| Manual gate | environment `required reviewers` | `when: manual` on a job + protected environment approvals |

The mental shift from GHA: **steps become shell lines**. There's no marketplace of composable Actions — a GitLab job is `image:` + `script:` and you write the commands yourself (or `include:` a template that does).

---

## stages / needs / rules — vs — jobs / needs / if

### Stages: the default ordering model

```yaml
stages: [lint, test, build, deploy]

lint-job:
  stage: lint
  script: [ruff check .]

unit-test:
  stage: test        # waits for ALL lint-stage jobs
  script: [pytest]
```

Stages are a coarse barrier: **every** job in `test` waits for **every** job in `lint`. Simple, readable — and slower than necessary for wide pipelines.

### `needs:` — turning stages into a DAG

```yaml
docker-build:
  stage: build
  needs: [unit-test]   # start as soon as unit-test passes,
                       # even if other test-stage jobs still run
```

With `needs:`, a job ignores the stage barrier and starts the moment its named dependencies pass — this is GitLab's **DAG pipelines** feature. Same keyword as GHA `needs`, but the delta is the default: GHA is parallel-unless-ordered, GitLab is staged-unless-DAG'd.

### `rules:` — GHA's `on:` + `if:` in one place

```yaml
deploy-prod:
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'
      when: on_success          # run automatically on main
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
      when: never               # never on MRs
    - when: manual              # anything else: manual button
```

Rules evaluate top-down, **first match wins**. One list controls whether the job exists in the pipeline at all, whether it's automatic/manual, and even `allow_failure` — where GHA splits this across `on:`, `if:`, and environment protection settings.

---

## Runners and Executors

| | GHA | GitLab |
|---|---|---|
| SaaS-hosted | GitHub-hosted runners (ephemeral VMs) | gitlab.com **shared runners** (compute-minute quota) |
| Self-hosted | self-hosted runners, matched by labels | **specific/project** and **group runners**, matched by `tags:` |
| Job isolation | whole VM per job (default) | depends on the runner's **executor** |

The concept GHA doesn't have: a GitLab runner is a single binary (`gitlab-runner`) whose **executor** decides HOW jobs run:

- **`shell`** — runs `script:` directly on the runner host. Fast, zero isolation; jobs pollute the host. Avoid except for controlled single-purpose boxes.
- **`docker`** — spins up the job's `image:` as a fresh container per job. The sane default; this is why `image:` is a first-class keyword.
- **`kubernetes`** — each job becomes a pod in your cluster; autoscaling for free (≈ GHA's Actions Runner Controller pattern, but built into the runner).

Jobs pick runners via `tags:` (≈ GHA `runs-on:` labels):

```yaml
gpu-training:
  tags: [gpu, linux]     # only runners registered with these tags pick it up
```

Same security caveat as GHA self-hosted runners: a shared-executor runner attached to a public project lets any MR author run code on your box — use ephemeral (docker/k8s) executors and protect runners for protected branches.

---

## What GitLab Genuinely Does Better

1. **Built-in container registry** — every project has one at `$CI_REGISTRY_IMAGE`, and CI jobs get auto-injected credentials (`$CI_REGISTRY_USER`/`$CI_REGISTRY_PASSWORD`). No PAT juggling, no separate GHCR setup — push in two lines.
2. **Environments + review apps** — `environment:` gives a deploy history UI with one-click rollback; a **review app** deploys every MR to a throwaway URL (`review/$CI_COMMIT_REF_SLUG`) and `on_stop:` tears it down when the MR merges. GHA can fake this; GitLab ships it.
3. **DAG pipelines** — `needs:` across stages (above) plus **parent-child pipelines** (`trigger:`) for monorepos: the parent generates or triggers a child pipeline per changed service.
4. **`include:` / templates** — compose your pipeline from local files, other projects, or GitLab's maintained templates (`template: Security/SAST.gitlab-ci.yml` gives you security scanning in one line). `extends:` then lets jobs inherit a base job definition — DRY at the YAML level, no marketplace needed.
5. **Auto DevOps** — a zero-config pipeline (detect language → build with buildpacks → test → scan → deploy to k8s). Real answer for interviews: great for demos and internal tools, most teams outgrow it and write explicit YAML — but its component templates are individually reusable via `include:`.

---

## Complete Realistic Pipeline — Python Service

Lint → test → build+push image → deploy, with pip caching and **OIDC to AWS** (no stored AWS keys — same principle as GHA's `id-token: write`, different mechanics: GitLab mints a JWT via `id_tokens:` and you exchange it yourself with STS).

```yaml
# .gitlab-ci.yml
stages: [lint, test, build, deploy]

workflow:                       # pipeline-level: avoid duplicate MR + branch pipelines
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
    - if: '$CI_COMMIT_BRANCH == "main"'

default:
  image: python:3.12-slim
  cache:                        # shared pip cache, keyed on lockfile
    key:
      files: [requirements.txt]
    paths: [.cache/pip]

variables:
  PIP_CACHE_DIR: "$CI_PROJECT_DIR/.cache/pip"
  IMAGE: "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA"

lint:
  stage: lint
  script:
    - pip install ruff
    - ruff check .

test:
  stage: test
  services:
    - postgres:16               # sidecar DB, reachable at host "postgres"
  variables:
    POSTGRES_PASSWORD: test
    DATABASE_URL: "postgresql://postgres:test@postgres:5432/postgres"
  script:
    - pip install -r requirements.txt -r requirements-dev.txt
    - pytest --junitxml=report.xml --cov=app
  artifacts:
    when: always                # publish report even on failure (≈ if: always())
    reports:
      junit: report.xml         # GitLab renders failures inline in the MR UI

build-image:
  stage: build
  needs: [test]                 # DAG: start as soon as test passes
  image: docker:27
  services:
    - docker:27-dind            # docker-in-docker daemon as a sidecar
  script:
    - echo "$CI_REGISTRY_PASSWORD" | docker login -u "$CI_REGISTRY_USER" --password-stdin "$CI_REGISTRY"
    - docker build -t "$IMAGE" .
    - docker push "$IMAGE"      # built-in registry — zero extra config
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'

deploy-prod:
  stage: deploy
  needs: [build-image]
  image: amazon/aws-cli:2.17.0
  environment:
    name: production
    url: https://api.example.com
  id_tokens:
    AWS_OIDC_TOKEN:             # GitLab mints a short-lived JWT into this var
      aud: https://gitlab.example.com
  variables:
    AWS_ROLE_ARN: arn:aws:iam::123456789012:role/gitlab-deploy   # trusts GitLab's OIDC provider
  script:
    - >
      export $(aws sts assume-role-with-web-identity
      --role-arn "$AWS_ROLE_ARN"
      --role-session-name "gitlab-$CI_PIPELINE_ID"
      --web-identity-token "$AWS_OIDC_TOKEN"
      --duration-seconds 3600
      --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]'
      --output text |
      xargs printf "AWS_ACCESS_KEY_ID=%s AWS_SECRET_ACCESS_KEY=%s AWS_SESSION_TOKEN=%s")
    - aws ecs update-service --cluster prod --service backend-api --force-new-deployment
  rules:
    - if: '$CI_COMMIT_BRANCH == "main"'
      when: manual              # human clicks "play" in the pipeline UI — deploy gate
```

Deltas worth saying out loud in an interview:
- **OIDC**: GHA hides the STS exchange inside `aws-actions/configure-aws-credentials`; in GitLab you declare `id_tokens:` and call `assume-role-with-web-identity` yourself. Same trust model (IAM role trusts the CI provider's OIDC issuer, conditions pin it to your project/branch), no long-lived keys either way.
- **`artifacts: reports: junit`** — GitLab consumes the report and shows failed tests directly in the MR widget; GHA needs a third-party action for that.
- **`when: manual` + `environment:`** — the approval gate lives on the job; GHA puts it on the environment's protection rules.

---

## Senior Tip

```
1. Pin included templates and images just like you'd pin GHA actions —
   `include: project: ..., ref: v2.1.0` — an unpinned remote include is
   the same supply-chain hole as `uses: something@main`.

2. Prefer `rules:` over the legacy `only:/except:` keywords everywhere.
   They can't be mixed in one job, and every modern feature (pipeline
   dedup via workflow:rules, `when: manual` per condition) is rules-only.

3. Mark secrets as Masked AND Protected in CI/CD variables — Protected
   means they're only injected on protected branches/tags, so a rogue
   feature-branch job can't exfiltrate prod credentials.

4. dind (docker:dind) requires privileged runners — a real attack
   surface on shared infra. Kaniko or buildah build images without a
   Docker daemon; know they exist and why (interviewers ask this).

5. Cache vs artifacts confusion is the #1 GitLab YAML bug: cache is a
   best-effort speed-up (per-runner, may be cold); artifacts are
   guaranteed hand-off between jobs. Never pass build outputs via cache.
```

## Interview Angle

**Q: "You've used Jenkins and GitHub Actions but not GitLab — how fast can you pick it up?"**
Days, not weeks — and prove it by mapping, not hand-waving: pipelines≈workflow runs, stages≈`needs`-chains, jobs+`script:`≈jobs+steps, `rules:`≈`on:`+`if:`, runners+executors≈GHA runners (with docker/k8s isolation built into the runner instead of always-a-VM), `include:`/`extends:`≈reusable workflows/composite actions, built-in registry≈GHCR with auto-auth. Then name one thing you'd actively use that GHA lacks — review apps per MR, or JUnit reports rendered in the MR widget — to show you've looked past the mapping.

**Q: "Stages already order jobs — why does `needs:` exist?"**
Stages are a barrier: every `build` job waits for ALL `test` jobs. `needs:` makes edges explicit so a job starts the moment ITS dependencies pass — in a pipeline with a slow integration-test job and a fast unit-test job, the image build behind `needs: [unit-test]` starts minutes earlier. Stages remain as visual grouping; `needs` turns execution into a DAG.

**Q: "Shared runner vs specific runner vs the executor — untangle those."**
Shared vs specific is WHO owns/scopes the runner (GitLab's SaaS fleet for everyone vs your machine registered to one project/group). Executor is HOW that runner runs a job: shell (on the host, no isolation), docker (fresh container per job — default choice), kubernetes (pod per job, autoscaling). Orthogonal axes: a specific runner can use any executor.

**Q: "How would you deploy a preview of every merge request, and clean it up on merge?"**
Review apps: a deploy job with `environment: name: review/$CI_COMMIT_REF_SLUG`, `url:` pointing at a per-branch host, and `on_stop:` referencing a teardown job (`when: manual`, `environment: action: stop`). GitLab links the live URL in the MR and auto-triggers the stop job when the branch is deleted/merged. In GHA you'd hand-roll all of this with deploy/comment/cleanup workflows.

**Q: "Your `.gitlab-ci.yml` is 600 lines and three teams keep stepping on each other — what do you do?"**
Split with `include:` — per-concern files (`ci/lint.yml`, `ci/deploy.yml`) or a central pipeline-templates project that service repos include with a pinned ref (the reusable-workflow pattern). Shared job skeletons become hidden base jobs (`.base-python:`) that concrete jobs `extends:`. In a monorepo, go further: parent-child pipelines with `trigger:` + `rules: changes:` so each service's child pipeline only runs when its directory changed.

---

## Related

- [`01_jenkins.md`](01_jenkins.md) — the self-hosted heavyweight; GitLab's stages ≈ Jenkins declarative stages, runners ≈ agents
- [`02_github_actions.md`](02_github_actions.md) — the baseline this delta is measured against; read it first
- [`../14_Security/03_iam_vuln_scanning.md`](../14_Security/03_iam_vuln_scanning.md) — the scanning GitLab's SAST/dependency-scanning templates bolt into a pipeline via one `include:`
- [`../20_Best_Practices/01_deployment_dr_incident_cost.md`](../20_Best_Practices/01_deployment_dr_incident_cost.md) — what `deploy-prod` above should actually do (canary/rolling), whatever CI triggers it
