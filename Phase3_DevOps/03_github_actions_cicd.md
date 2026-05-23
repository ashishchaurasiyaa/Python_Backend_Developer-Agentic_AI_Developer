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
