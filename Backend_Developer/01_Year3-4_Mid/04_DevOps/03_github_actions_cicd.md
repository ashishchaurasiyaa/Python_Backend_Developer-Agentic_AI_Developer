# GitHub Actions — CI/CD Pipeline

## Quick Concepts
- **GitHub Actions** = GitHub ka built-in CI/CD platform — free for public repos
- **Workflow** = `.github/workflows/*.yml` file — ek automated process
- **Job** = workflow ke andar independent unit (multiple jobs parallel run ho sakte hain)
- **Step** = job ke andar ek command ya action
- **Action** = reusable step (`actions/checkout`, `actions/setup-python`)
- **Secrets** = GitHub Settings mein store hote hain — env vars safely pass karne ke liye

---

## Interview Questions & Answers

### Q1: CI/CD kya hota hai? GitHub Actions mein basic workflow kaise likhte hain?
**Answer:**
- **CI (Continuous Integration)**: har code push par automatically test + build karo
- **CD (Continuous Deployment)**: test pass hone par automatically deploy karo

```yaml
# .github/workflows/ci.yml
name: CI Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run linting (Ruff)
        run: ruff check .

      - name: Run type checking (mypy)
        run: mypy app/

      - name: Run tests
        run: pytest tests/ -v --cov=app --cov-report=xml
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/testdb

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
```

---

### Q2: PostgreSQL aur Redis GitHub Actions mein kaise use karte hain (services)?
**Answer:**
```yaml
jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: testdb
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        ports:
          - 6379:6379
        options: --health-cmd "redis-cli ping" --health-interval 10s

    steps:
      - uses: actions/checkout@v4
      - name: Run tests with real DB
        run: pytest tests/
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/testdb
          REDIS_URL: redis://localhost:6379
```

---

### Q3: Docker build aur registry push kaise karte hain GitHub Actions mein?
**Answer:**
```yaml
# .github/workflows/build-push.yml
name: Build and Push Docker Image

on:
  push:
    branches: [main]
    tags: ["v*.*.*"]

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: myuser/myapp
          tags: |
            type=ref,event=branch
            type=semver,pattern={{version}}
            type=sha,prefix=sha-

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

---

### Q4: AWS EC2 par deploy kaise karte hain GitHub Actions se?
**Answer:**
```yaml
# .github/workflows/deploy.yml
name: Deploy to EC2

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    needs: [test]  # pehle test pass hona chahiye

    steps:
      - uses: actions/checkout@v4

      - name: Deploy to EC2 via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ubuntu
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd /home/ubuntu/myapp
            git pull origin main
            docker compose pull
            docker compose up -d --no-deps app
            docker system prune -f
```

**Secrets GitHub mein set karo:**
- `EC2_HOST` = EC2 public IP
- `EC2_SSH_KEY` = private key (`.pem` file ka content)
- `DOCKER_USERNAME`, `DOCKER_TOKEN` = Docker Hub credentials

---

### Q5: Matrix strategy kya hai? Multiple Python versions mein test kaise karte hain?
**Answer:**
```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
        os: [ubuntu-latest, macos-latest]
      fail-fast: false  # ek fail hone par baaki continue karein

    steps:
      - uses: actions/checkout@v4
      - name: Setup Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -r requirements.txt && pytest
```

---

### Q6: Reusable workflows aur secrets kaise kaam karte hain?
**Answer:**
```yaml
# .github/workflows/reusable-test.yml
on:
  workflow_call:
    inputs:
      environment:
        required: true
        type: string
    secrets:
      DATABASE_URL:
        required: true

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: pytest
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          ENV: ${{ inputs.environment }}

# Caller workflow:
jobs:
  call-tests:
    uses: ./.github/workflows/reusable-test.yml
    with:
      environment: staging
    secrets:
      DATABASE_URL: ${{ secrets.STAGING_DATABASE_URL }}
```

---

### Q7: Cache kaise use karte hain speed ke liye?
**Answer:**
```yaml
- name: Cache pip packages
  uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-

# Ya setup-python mein built-in cache:
- uses: actions/setup-python@v5
  with:
    python-version: "3.12"
    cache: "pip"           # automatic caching
```

---

### Q8: Build artifacts kya hote hain aur jobs ke beech data kaise pass karte hain?
**Answer:**

Artifacts = files produced by one job (build output, test reports, coverage
HTML) that need to survive after that job's runner is destroyed, either for
download by a human or for use by a LATER job in the same workflow.
Environment variables/`needs.<job>.outputs` only pass small strings between
jobs — actual FILES need artifacts.

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python -m build   # produces dist/*.whl, dist/*.tar.gz
      - name: Upload build artifact
        uses: actions/upload-artifact@v4
        with:
          name: python-package
          path: dist/
          retention-days: 7      # auto-deleted after N days — avoid unbounded storage cost

  test:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - run: pytest --cov=app --cov-report=html
      - name: Upload coverage report
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: htmlcov/

  deploy:
    needs: build            # deploy job re-uses what build job produced
    runs-on: ubuntu-latest
    steps:
      - name: Download build artifact
        uses: actions/download-artifact@v4
        with:
          name: python-package
          path: dist/
      - run: pip install dist/*.whl && deploy_script.sh
```

**Interview point:** artifacts let you build ONCE and deploy the EXACT same
built package to multiple later stages (staging → prod), instead of
rebuilding at each stage — rebuilding risks subtle differences (different
dependency resolution at a different time) between what was tested and what
actually ships. This is the CI/CD principle "build once, promote the same
artifact everywhere."

---

### Q9: Self-hosted runners kab use karte hain, GitHub-hosted runners ke bajaye?
**Answer:**

GitHub-hosted runners (`runs-on: ubuntu-latest`) are ephemeral VMs GitHub
provisions and destroys per job — zero maintenance, but limited specs, no
persistent state between runs, and can't reach your private network
(on-prem DB, internal VPC resources) without extra tunneling.

```yaml
jobs:
  build:
    runs-on: self-hosted   # or a custom label: [self-hosted, linux, gpu]
    steps:
      - uses: actions/checkout@v4
      - run: ./build.sh
```

```bash
# Registering a self-hosted runner (runs on YOUR infrastructure — a VM,
# an on-prem server, or a Kubernetes pod via actions-runner-controller)
./config.sh --url https://github.com/your-org/your-repo --token ABC123
./run.sh
```

| Need | Choice |
|---|---|
| Standard build/test, no special hardware | GitHub-hosted — zero maintenance |
| GPU-dependent jobs (ML model training/inference in CI) | Self-hosted with GPU |
| CI needs to reach a private VPC/on-prem database directly | Self-hosted, inside that network |
| Compliance requires build artifacts never leave your infrastructure | Self-hosted |
| Persistent build cache across runs without re-downloading each time | Self-hosted (GitHub-hosted runners are wiped clean every run) |

**Tradeoff to mention:** self-hosted runners are YOUR security responsibility
— a compromised self-hosted runner has whatever network access that machine
has, unlike GitHub-hosted runners which are fully isolated/destroyed per job.
Never use self-hosted runners for public/fork-triggered workflows without
careful guardrails (a malicious PR could run arbitrary code on your infra).

---

### Q10: Monorepo mein CI kaise design karte ho — har push par SAB services build na ho?
**Answer:**

A monorepo with multiple independent services (e.g., `services/api/`,
`services/worker/`, `services/frontend/`) shouldn't rebuild/retest
EVERYTHING on every single push — that wastes CI minutes and slows feedback.
**Path filtering** runs a job only when files in its relevant directory changed.

```yaml
# .github/workflows/ci.yml
on:
  push:
    branches: [main]
  pull_request:

jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      api: ${{ steps.filter.outputs.api }}
      worker: ${{ steps.filter.outputs.worker }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            api:
              - 'services/api/**'
            worker:
              - 'services/worker/**'

  test-api:
    needs: changes
    if: needs.changes.outputs.api == 'true'   # only runs if api/ actually changed
    runs-on: ubuntu-latest
    steps:
      - run: cd services/api && pytest

  test-worker:
    needs: changes
    if: needs.changes.outputs.worker == 'true'
    runs-on: ubuntu-latest
    steps:
      - run: cd services/worker && pytest
```

**Alternative — native path filters on the trigger itself** (simpler, but
less flexible than the `dorny/paths-filter` job-output pattern above, since
it can only gate the WHOLE workflow, not individual jobs within one):

```yaml
on:
  push:
    paths:
      - 'services/api/**'
```

**Interview point:** the job-output pattern (via `paths-filter` action) is
preferred over trigger-level `paths:` in real monorepos because a single PR
often touches MULTIPLE services — trigger-level filtering runs the whole
workflow-or-nothing, while the job-output pattern lets you selectively run
`test-api` AND `test-worker` in the SAME workflow run when both changed, and
skip whichever one didn't.

---

## Complete CI/CD Pipeline Example (Production-ready)

```yaml
name: Full CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env: {POSTGRES_PASSWORD: postgres, POSTGRES_DB: testdb}
        ports: ["5432:5432"]
        options: --health-cmd pg_isready --health-interval 5s --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12", cache: "pip"}
      - run: pip install -r requirements.txt
      - run: ruff check . && mypy app/
      - run: pytest --cov=app
        env: {DATABASE_URL: "postgresql://postgres:postgres@localhost:5432/testdb"}

  deploy:
    needs: test
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_TOKEN }}
      - uses: docker/build-push-action@v5
        with:
          push: true
          tags: myuser/myapp:${{ github.sha }},myuser/myapp:latest
      - uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ubuntu
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            docker pull myuser/myapp:latest
            docker compose up -d --no-deps app
```
