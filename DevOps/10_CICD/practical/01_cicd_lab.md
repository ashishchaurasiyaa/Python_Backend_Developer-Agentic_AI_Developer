# CI/CD — Hands-On Lab
**DevOps Track · Phase 10 Practical**

## Prerequisites

- A free GitHub account and a small public/private repo to experiment in — GitHub Actions is **free** on public repos (and gives a generous free minutes allowance on private ones), no cost to complete this whole lab
- A simple Python project to build/test against — a minimal FastAPI or Flask app with 2-3 `pytest` tests is enough; if you don't have one handy, `pip install fastapi pytest httpx` and write 10 lines of app + 10 lines of test
- Docker installed locally, for both the Jenkins labs and building/scanning container images
- For the Jenkins portion: no cloud cost required — Jenkins runs locally via Docker (`jenkins/jenkins:lts` image, covered below)
- Optional (Lab 3): a free Docker Hub account if you want to actually push an image somewhere, or just build+scan locally without pushing — the security-gate concept doesn't require a real registry

Both Jenkins and GitHub Actions are covered — GitHub Actions labs assume you have a GitHub repo to push to; Jenkins labs run entirely on your machine.

---

## Lab 1: GitHub Actions — Lint → Test on Every Push

**Objective:** Get a real, working CI workflow gating pushes/PRs — the baseline every repo should have before anything fancier.

**Task:**
1. In your repo, create `.github/workflows/ci.yml`.
2. Trigger on `push` to `main` and on every `pull_request` targeting `main`.
3. One job, `test`, running on `ubuntu-latest`: checkout code, set up Python 3.12, install `ruff` and your project's requirements, run `ruff check .`, then run `pytest`.
4. Push the workflow file and confirm it runs automatically in the Actions tab.
5. Deliberately break a test (assert something false) in a new branch, open a PR, and confirm GitHub shows a red "X" status check blocking the PR — then fix it and watch it go green.
6. Go to Settings → Branches and add a branch protection rule on `main` requiring this check to pass before merging.

<details>
<summary>Solution / walkthrough</summary>

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install ruff pytest
          pip install -r requirements.txt

      - name: Lint
        run: ruff check .

      - name: Test
        run: pytest
```

**Why this order (lint before test):** a lint failure is nearly free to detect (no test execution needed) — failing fast on lint saves CI minutes versus running the full test suite first and discovering a formatting issue afterward. `cache: 'pip'` in `setup-python` caches installed dependencies between runs, which matters because slow CI is a daily productivity tax on the whole team, not a one-time cost.

Branch protection turns "the test passed" from a suggestion into an enforced gate — nobody can merge a PR with a red check, which is the actual point of CI (catching regressions before `main`, not just after).
</details>

---

## Lab 2: Matrix Testing + Artifacts + Docker Build

**Objective:** Scale the pipeline to test across multiple Python versions in parallel and produce a build artifact — the two features that separate a toy workflow from a real one.

**Task:**
1. Extend Lab 1's `test` job into a matrix over `python-version: ['3.11', '3.12']`, with `fail-fast: false` so both versions' failures are visible independently.
2. Upload the `pytest` JUnit XML report as an artifact per matrix leg (name it uniquely per Python version so they don't overwrite each other), using `if: always()` so it uploads even on failure.
3. Add a `Dockerfile` for your app (multi-stage: install deps in a builder stage, copy into a slim runtime stage).
4. Add a second job, `build`, that `needs: test`, builds the Docker image, and tags it with the git SHA (`${{ github.sha }}`).
5. Confirm in the Actions UI: two parallel `test` legs, then `build` waiting for both before starting.

<details>
<summary>Solution / walkthrough</summary>

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ['3.11', '3.12']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'
      - run: pip install -r requirements.txt pytest
      - run: pytest --junitxml=results.xml
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results-${{ matrix.python-version }}
          path: results.xml

  build:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: docker build -t myapp:${{ github.sha }} .
```

```dockerfile
# Dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --target=/app/deps -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app/deps /app/deps
COPY . .
ENV PYTHONPATH=/app/deps
CMD ["python", "main.py"]
```

**Why `fail-fast: false` here specifically:** without it, the FIRST failing matrix leg cancels the others — you'd only ever see one failure at a time across Python versions, which is exactly backwards for a library/app that needs to work on multiple versions. You want to see ALL the breakage in one CI run, not discover it one version at a time over several pushes.

**Why `needs: test` on build:** there's no point building a Docker image around code that doesn't even pass its own tests — `needs` creates that explicit dependency so `build` never runs against known-broken code.
</details>

---

## Lab 3: Production-Style Pipeline — Fail the Build on a Failed Security Scan

**Objective:** Wire in the pattern from `../14_Security/03_iam_vuln_scanning.md` — an image that has a HIGH/CRITICAL CVE never reaches a registry a cluster could pull from. This is the pipeline shape a real production team runs.

**Task:**
1. Extend Lab 2's `build` job (or add a new `scan` job that `needs: build`) to scan the built image with Trivy (`aquasecurity/trivy-action`).
2. Configure the scan to fail the job (`exit-code: 1`) on `HIGH,CRITICAL` severity, ignoring unfixed CVEs (`ignore-unfixed: true`).
3. Add a `push` job that `needs: scan` — it should only run if the scan job succeeded (this is automatic via `needs`, but confirm you understand why).
4. Deliberately use an old/vulnerable base image (e.g. `python:3.9-slim` instead of the current slim tag, or `ubuntu:20.04`) to trigger real findings, and confirm the pipeline actually goes red at the scan step, not just in theory.
5. Fix it by bumping to a current base image, re-run, confirm scan passes and `push` now runs.
6. Add `environment: production` to the push/deploy job and configure a required reviewer in GitHub Settings → Environments, so a human must click Approve before a deploy job actually executes — the real-world deploy gate.

<details>
<summary>Solution / walkthrough</summary>

```yaml
name: CI/CD with Security Gate

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt pytest
      - run: pytest

  build:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: docker build -t myapp:${{ github.sha }} .
      - name: Save image as artifact for the scan job
        run: docker save myapp:${{ github.sha }} -o image.tar
      - uses: actions/upload-artifact@v4
        with:
          name: docker-image
          path: image.tar

  scan:
    runs-on: ubuntu-latest
    needs: build
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: docker-image
      - run: docker load -i image.tar
      - name: Scan image with Trivy
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: myapp:${{ github.sha }}
          format: table
          severity: HIGH,CRITICAL
          exit-code: 1
          ignore-unfixed: true

  push:
    runs-on: ubuntu-latest
    needs: scan
    if: github.ref == 'refs/heads/main'
    environment: production   # requires manual approval if configured in Settings > Environments
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: docker-image
      - run: docker load -i image.tar
      - name: Log in to Docker Hub
        run: echo "${{ secrets.DOCKERHUB_TOKEN }}" | docker login -u "${{ secrets.DOCKERHUB_USERNAME }}" --password-stdin
      - name: Push image
        run: |
          docker tag myapp:${{ github.sha }} yourdockerhubuser/myapp:${{ github.sha }}
          docker push yourdockerhubuser/myapp:${{ github.sha }}
```

**What happens with a deliberately old base image:** the `scan` job's Trivy step exits non-zero, the job fails, GitHub Actions never runs `push` because its `needs: scan` dependency didn't succeed — no manual intervention required to block it, the DAG itself enforces the gate. This is the exact "shift-left" pattern from the security lesson file: catching a CRITICAL CVE in a PR/build blocks it before it's ever pushed to a registry a cluster could pull from, instead of finding out after it's already running in production.

**Bonus — Jenkins equivalent of the same gate**, for comparison (run against your local Docker Jenkins from the setup step):
```groovy
pipeline {
    agent any
    stages {
        stage('Build') {
            steps { sh 'docker build -t myapp:${BUILD_NUMBER} .' }
        }
        stage('Scan') {
            steps {
                sh 'trivy image --severity HIGH,CRITICAL --exit-code 1 --ignore-unfixed myapp:${BUILD_NUMBER}'
            }
        }
        stage('Push') {
            when { branch 'main' }
            steps { sh 'docker push myapp:${BUILD_NUMBER}' }
        }
    }
}
```
Same shape, same guarantee — a failed `sh` step in a Declarative pipeline stage fails the whole build and later stages never run, exactly like `needs` gating downstream jobs in GitHub Actions.
</details>

---

## Lab 4: Troubleshooting — Debugging a Failing Matrix Leg and a Silent Webhook

**Objective:** Practice two of the most common real CI/CD debugging scenarios.

**Task (Part A — matrix leg):**
1. In your Lab 2 matrix workflow, introduce a bug that only manifests on Python 3.11 (e.g. use a 3.12-only syntax feature, or a dict-merge behavior that differs).
2. From the Actions UI, use "Re-run failed jobs" to re-run only the broken leg, not the whole matrix.
3. Reproduce the failure locally with the exact same Python version pinned (`pyenv install 3.11` or a `python3.11` venv) to confirm you can debug it outside CI.

**Task (Part B — Jenkins webhook not firing):**
1. Start the local Jenkins container from the prerequisites, create a Pipeline job pointed at a GitHub repo, and configure the `githubPush()` trigger.
2. Push a commit and observe that the build does NOT start (expected — your local Jenkins isn't reachable from GitHub's servers over the internet).
3. Diagnose why: GitHub's webhook delivery requires a publicly reachable URL; explain what you'd need (a public Jenkins URL, or a tunnel like `ngrok` for local dev) and why this is a non-issue once Jenkins runs behind a real domain in production.
4. As a workaround for this lab, trigger the build manually or via SCM polling (`pollSCM('H/5 * * * *')`) and confirm the pipeline itself still works correctly — the webhook is a delivery mechanism, not the pipeline logic.

<details>
<summary>Solution / walkthrough</summary>

**Part A:**
```yaml
# Deliberately 3.12-only syntax (PEP 695 type alias, for example)
type IntList = list[int]
```
Running this under the `python-version: '3.11'` matrix leg fails with a `SyntaxError`, while `3.12` passes — exactly the kind of version-specific bug matrix testing exists to catch before a user on an older Python hits it in production. From the Actions UI: Actions tab → the failed run → "Re-run jobs" → "Re-run failed jobs" reruns only the 3.11 leg, saving the time of re-running the already-passing 3.12 leg.

Local repro:
```bash
python3.11 -m venv venv311 && source venv311/bin/activate
pip install -r requirements.txt pytest
pytest   # reproduces the exact same SyntaxError locally
```

**Part B:**
```bash
docker run -d --name jenkins -p 8080:8080 -p 50000:50000 -v jenkins_home:/var/jenkins_home jenkins/jenkins:lts
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```
After creating the pipeline job with `triggers { githubPush() }`, a push to GitHub silently does nothing locally — because GitHub's webhook is an outbound HTTP call FROM GitHub's servers TO your Jenkins URL, and `http://localhost:8080` on your laptop isn't reachable from the public internet at all.

Real fix for local dev/testing: `ngrok http 8080`, then set the GitHub webhook payload URL to the ngrok-provided public URL + `/github-webhook/`. Real fix for production: Jenkins sits behind an actual public URL/load balancer, so this problem simply doesn't exist once deployed properly — the lesson file calls this out explicitly ("Jenkins must be reachable from GitHub's servers").

Workaround to unblock the lab without a tunnel:
```groovy
pipeline {
    agent any
    triggers {
        pollSCM('H/5 * * * *')   // check for new commits every ~5 minutes instead of webhook push
    }
    stages { /* ... */ }
}
```
`pollSCM` is strictly worse than a webhook (slower, wastes cycles checking when nothing changed) but proves the pipeline logic itself is correct, independent of the trigger mechanism — a useful way to isolate "is my pipeline broken" from "is my trigger broken" when debugging.
</details>

---

## Self-Check Checklist

- [ ] Can you write a GitHub Actions workflow with `push`/`pull_request` triggers and a lint-then-test job from memory?
- [ ] Can you explain what `needs:` does and write a 3-job DAG (lint → test → build) using it?
- [ ] Can you explain why `fail-fast: false` matters for a matrix build testing multiple versions?
- [ ] Can you explain why artifacts exist (what problem do they solve that env vars/outputs don't)?
- [ ] Can you explain the three secret scopes (environment/repo/org) and which wins when they overlap?
- [ ] Can you wire a Trivy scan into a pipeline so a HIGH/CRITICAL CVE blocks the build, and explain why `needs`/stage-ordering is what actually enforces the gate?
- [ ] Can you explain OIDC-based cloud auth (`role-to-assume`) and why it's preferred over storing static `AWS_SECRET_ACCESS_KEY` as a secret?
- [ ] Can you explain the Jenkins controller/agent split and why running builds directly on the controller is a known anti-pattern?
- [ ] Can you explain what a Jenkins Shared Library solves, and when a team should adopt one?
- [ ] Can you diagnose "my GitHub webhook isn't triggering my local Jenkins" without looking it up?
