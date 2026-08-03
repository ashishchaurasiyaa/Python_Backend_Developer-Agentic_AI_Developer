# CI/CD — GitHub Actions
**DevOps Track · Phase 10: CI/CD**

> Complementary to Backend_Developer/01_Year3-4_Mid/04_DevOps/ (app-deployment angle) — this covers the fuller tool/architecture picture.

## Quick Concepts

- **Workflow** = a YAML file in `.github/workflows/` describing automated steps, triggered by events
- **Event/Trigger** = what starts a workflow — `push`, `pull_request`, `schedule`, `workflow_dispatch`, etc.
- **Job** = a set of steps that run on the same runner; jobs run in parallel by default, in isolated VMs/containers
- **Step** = a single command or a reusable **Action** (`uses: actions/checkout@v4`)
- **Runner** = the machine executing a job — GitHub-hosted (ephemeral VM GitHub manages) or self-hosted (your own machine registered to the repo/org)
- **Matrix Build** = one job definition fanned out across a grid of variable combinations (e.g., 3 Python versions × 2 OSes = 6 parallel jobs)
- **Artifact** = a file/directory produced by one job and persisted for download or use by another job in the same workflow run
- **Secret** = an encrypted value (API key, token) stored at repo/environment/org level, injected into a step via `${{ secrets.NAME }}`, never printed in logs
- **Environment** = a named deployment target (e.g., `production`) with its own secrets, required reviewers, and wait timers
- **Reusable workflow** = a whole job, defined once (`workflow_call`), invoked from many workflows/repos with different inputs
- **Composite action** = a reusable sequence of steps dropped into an existing job — lighter-weight than a reusable workflow
- **Concurrency group** = a key that cancels or queues overlapping workflow runs instead of letting them all run wastefully in parallel

---

## Why This Matters

```
GitHub Actions is the default CI/CD for anything already on GitHub —
no separate server to run, YAML lives next to the code, huge
marketplace of reusable Actions.

As a backend+DevOps engineer you're expected to author full pipelines,
not just "add a test step": lint -> test -> build image -> push to a
registry -> deploy, with matrix testing, secrets scoped correctly,
and artifacts passed between jobs. That's the bar this file covers.
```

---

## Workflow YAML Structure

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 3 * * *'      # nightly at 03:00 UTC
  workflow_dispatch:          # manual "Run workflow" button in the UI
    inputs:
      environment:
        description: 'Target environment'
        required: true
        default: 'staging'
        type: choice
        options: [staging, production]

jobs:
  example:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "hello"
```

### Trigger Notes

| Trigger | Fires on | Common use |
|---|---|---|
| `push` | commit pushed to matching branch/tag | run tests on every commit |
| `pull_request` | PR opened/updated against target branch | gate merges — required status check |
| `schedule` | cron expression (UTC only) | nightly builds, dependency audits, cleanup jobs |
| `workflow_dispatch` | manual trigger from UI/API | on-demand deploys, one-off scripts |
| `release` | a GitHub Release is published | publish packages, build final artifacts |
| `workflow_call` | invoked by another workflow | reusable workflows |

---

## Jobs: Dependencies with `needs`

By default all jobs in a workflow run in parallel. `needs` creates an explicit DAG:

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install ruff && ruff check .

  test:
    runs-on: ubuntu-latest
    needs: lint                # waits for lint to pass first
    steps:
      - uses: actions/checkout@v4
      - run: pytest

  build:
    runs-on: ubuntu-latest
    needs: [lint, test]        # waits for BOTH
    steps:
      - run: echo "building..."

  deploy:
    runs-on: ubuntu-latest
    needs: build
    if: github.ref == 'refs/heads/main'   # only deploy from main
    steps:
      - run: echo "deploying..."
```

`needs` also exposes upstream job outputs: `${{ needs.build.outputs.image_tag }}` — useful for passing a computed value (like a Docker tag) down the chain.

---

## Matrix Builds — Real Example

```yaml
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false            # don't cancel other combos if one fails
      matrix:
        os: [ubuntu-latest, macos-latest]
        python-version: ['3.10', '3.11', '3.12']
        exclude:
          - os: macos-latest
            python-version: '3.10'
        include:
          - os: ubuntu-latest
            python-version: '3.12'
            experimental: true

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -r requirements.txt
      - run: pytest
```

This fans out into 5 parallel jobs (2×3 minus 1 excluded). `matrix.<key>` is interpolated per-job; `fail-fast: false` is important for library maintainers who want to see failures across ALL supported versions, not just the first one.

---

## Secrets

Three scopes, checked in this priority order (most specific wins):

| Scope | Set at | Visible to |
|---|---|---|
| **Environment secret** | Repo → Settings → Environments → `production` | jobs targeting that environment, can require manual approval before use |
| **Repository secret** | Repo → Settings → Secrets and variables → Actions | all workflows in that repo |
| **Organization secret** | Org → Settings → Secrets | selected repos across the org (central rotation point) |

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production        # pulls production-scoped secrets,
                                    # can require reviewer approval
    steps:
      - name: Deploy
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          aws s3 sync ./dist s3://my-bucket/
```

Secrets are automatically masked in logs (`***`) even if a step accidentally echoes them. Never pass secrets as CLI arguments visible in `ps` output on shared runners — prefer env vars or files.

---

## Artifacts

Artifacts pass build output between jobs (which run on separate, isolated VMs and don't share a filesystem) or let you download output from the Actions UI after a run.

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          pip install build
          python -m build
      - name: Upload dist
        uses: actions/upload-artifact@v4
        with:
          name: python-dist
          path: dist/
          retention-days: 7

  publish:
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Download dist
        uses: actions/download-artifact@v4
        with:
          name: python-dist
          path: dist/
      - run: twine upload dist/*
```

Common uses: test reports (JUnit XML) for later inspection, coverage HTML reports, compiled binaries, Docker image tarballs passed to a scan job before push.

---

## Self-Hosted Runners

GitHub-hosted runners are ephemeral VMs GitHub provisions per job (clean every time, but limited CPU/RAM, no access to your private network, minutes are metered/billed on private repos). Self-hosted runners are machines **you** register and maintain.

**Use self-hosted when:**
- You need access to private network resources (internal DB, VPN-only services) during CI
- You need specific hardware (GPUs for ML training, ARM builds, more RAM/CPU than hosted tiers offer)
- You're running high job volume and hosted-runner minutes get expensive
- You need a custom pre-baked image with heavy tooling that's slow to reinstall every run

**Trade-off**: you now own patching, scaling, and security isolation. A self-hosted runner attached to a **public** repo is a real security risk — anyone who can open a PR can potentially run code on your infrastructure via a malicious workflow change; GitHub disables self-hosted runners on public repo forks by default for this reason.

```yaml
jobs:
  build:
    runs-on: [self-hosted, linux, gpu]   # match by custom labels
    steps:
      - uses: actions/checkout@v4
      - run: ./train_model.sh
```

Modern setups often run self-hosted runners as ephemeral Kubernetes pods (via **Actions Runner Controller**) so each job still gets a clean environment, combining self-hosted network access with hosted-style disposability.

---

## Reusable Workflows and Composite Actions — Actually DRYing Up CI

The trigger table earlier named `workflow_call` in passing. Here's what building and calling one actually looks like — the fix for "we copy-pasted this same lint+test+build sequence into 12 repos."

### Reusable Workflow — Shared Across Repos

```yaml
# .github/workflows/reusable-deploy.yml (lives in a shared/central repo, or this same repo)
name: Reusable Deploy

on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
      image-tag:
        required: true
        type: string
    secrets:
      AWS_DEPLOY_ROLE_ARN:
        required: true

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
          aws-region: ap-south-1
      - run: aws ecs update-service --cluster prod --service api --force-new-deployment
```

```yaml
# .github/workflows/deploy-staging.yml — the CALLING workflow, in any repo
name: Deploy Staging
on:
  push:
    branches: [main]

jobs:
  call-deploy:
    uses: my-org/shared-workflows/.github/workflows/reusable-deploy.yml@v1   # pinned version
    with:
      environment: staging
      image-tag: ${{ github.sha }}
    secrets:
      AWS_DEPLOY_ROLE_ARN: ${{ secrets.STAGING_DEPLOY_ROLE_ARN }}
```

```
inputs/secrets on `workflow_call` are EXPLICIT — the reusable workflow
declares exactly what it needs, the caller must supply it. This is the
whole point: a platform team maintains ONE deploy workflow, every
service's repo just calls it with different parameters, and a fix to
the deploy logic (a new required scan step, say) updates every
consumer the next time they bump the pinned `@v1` reference.
```

### Composite Actions — Reusable Steps WITHIN One Repo

A reusable workflow is a whole JOB you call. A **composite action** is a reusable SEQUENCE OF STEPS you can drop into any job, in the same or another repo — the right granularity when you just want to DRY up a few repeated steps, not an entire job.

```yaml
# .github/actions/setup-python-app/action.yml
name: 'Setup Python App'
description: 'Checkout, setup Python, install deps with caching'
inputs:
  python-version:
    required: false
    default: '3.12'
runs:
  using: "composite"
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: ${{ inputs.python-version }}
        cache: 'pip'
    - run: pip install -r requirements.txt -r requirements-dev.txt
      shell: bash    # composite action steps MUST specify shell explicitly
```

```yaml
# any workflow, using the composite action above
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: ./.github/actions/setup-python-app
        with:
          python-version: '3.11'
      - run: pytest
```

```
Reusable workflow vs composite action — the distinction that matters:
  reusable workflow  → a whole JOB (its own runner, its own permissions/
                        secrets scope), called with `uses:` at the JOB level
  composite action    → a few STEPS, inlined into an EXISTING job, called
                          with `uses:` at the STEP level — no separate
                          runner, shares the calling job's context entirely
```

### Concurrency Control — Cancelling Stale Runs

Without this, pushing 3 commits in quick succession to the same branch queues (or runs) 3 full pipeline executions — wasting runner minutes on commits that are already obsolete by the time they'd finish.

```yaml
name: CI

on:
  push:
    branches: [main, 'feature/**']

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true    # a NEW push to the same branch cancels
                                # any run already in progress for it

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: pytest
```

```
group: ci-${{ github.workflow }}-${{ github.ref }}  → the group key
scopes concurrency PER BRANCH — pushes to feature/login don't cancel
a run on feature/checkout, only a NEWER push to that SAME branch/ref.

cancel-in-progress: true is the right default for CI test runs (the
old commit's results are moot once superseded); it's usually the
WRONG setting for a deploy workflow — you don't want a deploy to
production cancelled halfway through by a queued-up second deploy,
you want deploys to queue and run one at a time instead (omit
cancel-in-progress, or set it false, for those).
```

---

## Full Real Workflow: Lint → Test → Build Docker Image → Push to ECR

```yaml
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  AWS_REGION: ap-south-1
  ECR_REPOSITORY: backend-api

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install ruff
      - run: ruff check .

  test:
    runs-on: ubuntu-latest
    needs: lint
    strategy:
      matrix:
        python-version: ['3.11', '3.12']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest --junitxml=results.xml --cov=app
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results-${{ matrix.python-version }}
          path: results.xml

  build-and-push:
    runs-on: ubuntu-latest
    needs: test
    if: github.ref == 'refs/heads/main'
    environment: production
    permissions:
      id-token: write     # required for OIDC-based AWS auth
      contents: read
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: ecr-login
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build, tag, and push image
        env:
          ECR_REGISTRY: ${{ steps.ecr-login.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest

      - name: Deploy to ECS
        run: |
          aws ecs update-service \
            --cluster prod-cluster \
            --service backend-api \
            --force-new-deployment
```

Notes on this workflow:
- `aws-actions/configure-aws-credentials` with `role-to-assume` uses **OIDC** — no long-lived AWS keys stored as secrets at all, GitHub exchanges a short-lived token for temporary AWS credentials. This is the modern, preferred pattern over storing `AWS_SECRET_ACCESS_KEY`.
- `environment: production` means this job can require manual approval (a human clicks "Approve" in the UI) before running — a real deploy gate.
- `test` runs a matrix so both supported Python versions are verified before anything reaches `main`-gated build/push.

---

## Senior Tip

```
1. Pin action versions to a SHA or major version tag you trust
   (uses: actions/checkout@v4, not @main) — a compromised marketplace
   action with @main can inject malicious code into your pipeline.

2. Use `permissions:` to scope the GITHUB_TOKEN down from its
   dangerous default (contents: write, etc.) to only what's needed
   (contents: read) — least privilege at the workflow level.

3. Cache dependencies (`cache: 'pip'` in setup-python, or
   actions/cache@v4 directly) — CI time is developer feedback-loop
   time, and slow CI is a productivity tax the whole team pays daily.

4. Prefer OIDC over long-lived cloud credentials in secrets — a leaked
   OIDC role has a blast radius limited to what that role can do and
   expires quickly; a leaked static AWS key is valid until rotated.

5. `if: always()` on artifact-upload/notification steps so test
   reports still get published even when the test step itself fails.
```

## Interview Angle

**Q: "How do you prevent a workflow from deploying on every PR from a fork?"**
Use `pull_request_target` cautiously (it runs with base-repo secrets — dangerous with untrusted PR code) or, safer, gate deploy jobs with `if: github.ref == 'refs/heads/main' && github.event_name == 'push'` so forked PRs never reach the deploy job, and require environment approval for anything touching prod secrets.

**Q: "Matrix build fails on one combination — how do you debug just that leg?"**
Re-run failed jobs individually from the Actions UI (`Re-run failed jobs`), or use `matrix.<key>` values in step names/logs so failures are unambiguous; locally reproduce with the same `python-version`/`os` pinned.

**Q: "This pipeline builds and pushes an image — how does it actually get deployed to the cluster?"**
Two legitimate patterns, know the tradeoff: (1) the pipeline itself runs the deploy step (`kubectl apply` / `helm upgrade` / `aws ecs update-service`, as shown above) — simpler, but the CI system now needs cluster/cloud credentials, and there's no single source of truth for "what's actually running" beyond pipeline logs; (2) GitOps (ArgoCD/Flux) — the pipeline only builds and pushes the image (or updates an image tag in a separate Git repo), and a cluster-side operator pulls and reconciles — no cluster credentials ever leave the cluster, and Git becomes the auditable source of truth. Full depth: [`Backend_Developer/01_Year3-4_Mid/04_DevOps/13_gitops_argocd_flux.md`](../../Backend_Developer/01_Year3-4_Mid/04_DevOps/13_gitops_argocd_flux.md).

**Q: "12 different repos all have nearly identical lint+test+build+deploy workflows. How do you avoid maintaining 12 copies?"**
Depends on the granularity of duplication. If it's a WHOLE deploy job repeated across repos, extract it into a reusable workflow (`on: workflow_call`) in a shared repo, and have each service's workflow call it with `uses: org/shared-workflows/.github/workflows/deploy.yml@v1` plus its own `inputs`/`secrets`. If it's just a few repeated STEPS within an otherwise-different job (checkout + setup + cached install, say), a composite action (`.github/actions/*/action.yml`) is the lighter-weight fix — reusable at the step level instead of the job level.

**Q: "Someone pushes 3 commits in quick succession to a feature branch, and CI runs (and burns runner minutes on) all 3, even though only the last one matters." How do you fix this?**
Add a `concurrency` block keyed on the branch/ref (`group: ci-${{ github.ref }}`) with `cancel-in-progress: true` — a new push to the same branch automatically cancels whatever CI run was already in progress for it, since its results are moot the moment a newer commit lands. The important caveat: `cancel-in-progress: true` is usually the WRONG setting for a deploy workflow, where you want overlapping deploys to queue and run one at a time, not have one killed mid-deploy by a newer one starting.

---

## Related

- [`../06_Kubernetes/05_helm.md`](../06_Kubernetes/05_helm.md) — what `helm upgrade --install` (a common deploy step here) actually does
- [`Backend_Developer/01_Year3-4_Mid/04_DevOps/13_gitops_argocd_flux.md`](../../Backend_Developer/01_Year3-4_Mid/04_DevOps/13_gitops_argocd_flux.md) — pull-based GitOps as the alternative to this file's push-based deploy step
- [`../14_Security/03_iam_vuln_scanning.md`](../14_Security/03_iam_vuln_scanning.md) — image scanning + SBOM generation as pipeline steps before push
- [`../20_Best_Practices/01_deployment_dr_incident_cost.md`](../20_Best_Practices/01_deployment_dr_incident_cost.md) — canary/rolling/blue-green strategy for what happens after this pipeline deploys
