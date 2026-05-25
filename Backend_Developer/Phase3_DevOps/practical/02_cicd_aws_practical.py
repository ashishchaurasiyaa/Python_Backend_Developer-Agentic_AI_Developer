"""
Phase3_DevOps — CI/CD + AWS Practical
=======================================
Topics covered:
  1. GitHub Actions workflows (test, lint, build, deploy)
  2. Docker build + push to ECR via GitHub Actions
  3. boto3: S3 operations (upload, download, presigned URL)
  4. boto3: SQS send/receive messages
  5. boto3: EC2/RDS patterns
  6. Zero-downtime deployment strategies
  7. Secrets management in CI/CD

Run:
  pip install boto3
  python 02_cicd_aws_practical.py
"""

import os
import json

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: GitHub Actions — Python CI Pipeline
# INTERVIEW: .github/workflows/ci.yml
# ─────────────────────────────────────────────────────────────────────────────

CI_WORKFLOW = """\
# .github/workflows/ci.yml
name: CI Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

# INTERVIEW: Concurrency = cancel running workflow when new push arrives
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  # ── Lint ─────────────────────────────────────────────────────────
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Install deps
        run: uv sync --dev

      - name: Ruff lint
        run: uv run ruff check .

      - name: Ruff format check
        run: uv run ruff format --check .

      - name: mypy
        run: uv run mypy app/

  # ── Tests ────────────────────────────────────────────────────────
  test:
    runs-on: ubuntu-latest
    needs: lint   # only run if lint passes

    # INTERVIEW: services = docker containers available during tests
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER:     test
          POSTGRES_PASSWORD: test
          POSTGRES_DB:       testdb
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    env:
      DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/testdb
      REDIS_URL:    redis://localhost:6379/0
      SECRET_KEY:   test-secret-key-min-32-chars-here

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      # INTERVIEW: Cache dependencies for faster CI
      - name: Cache uv
        uses: actions/cache@v4
        with:
          path: ~/.cache/uv
          key: ${{ runner.os }}-uv-${{ hashFiles('uv.lock') }}

      - run: uv sync --dev

      - name: Run tests with coverage
        run: uv run pytest tests/ -v --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
          token: ${{ secrets.CODECOV_TOKEN }}

  # ── Build & Push Docker Image ────────────────────────────────────
  build-push:
    runs-on: ubuntu-latest
    needs: test
    if: github.ref == 'refs/heads/main'   # Only on main branch

    permissions:
      id-token: write   # OIDC auth to AWS (no long-lived keys!)
      contents: read

    steps:
      - uses: actions/checkout@v4

      # INTERVIEW: OIDC = no AWS_ACCESS_KEY stored in GitHub secrets
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789:role/github-actions-role
          aws-region: us-east-1

      - name: Login to ECR
        id: ecr-login
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: |
            ${{ steps.ecr-login.outputs.registry }}/myapp:latest
            ${{ steps.ecr-login.outputs.registry }}/myapp:${{ github.sha }}
          cache-from: type=gha    # GitHub Actions cache
          cache-to:   type=gha,mode=max

  # ── Deploy to ECS ────────────────────────────────────────────────
  deploy:
    runs-on: ubuntu-latest
    needs: build-push
    environment: production   # Requires manual approval in GitHub

    steps:
      - name: Deploy to ECS
        uses: aws-actions/amazon-ecs-deploy-task-definition@v2
        with:
          task-definition: task-def.json
          service:         myapp-service
          cluster:         myapp-cluster
          wait-for-service-stability: true
"""

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: boto3 — S3 Operations
# INTERVIEW: S3 = object storage (files, images, backups)
# ─────────────────────────────────────────────────────────────────────────────

def demo_s3():
    """S3 operations: upload, download, presigned URLs."""
    print("\n[S3 Operations Demo]")

    try:
        import boto3
        from botocore.exceptions import ClientError

        s3 = boto3.client(
            "s3",
            region_name          = os.getenv("AWS_REGION", "us-east-1"),
            aws_access_key_id    = os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
        bucket = os.getenv("S3_BUCKET", "my-app-bucket")

        print(f"  S3 client created (bucket: {bucket})")

        # Upload file
        # s3.upload_file(
        #     Filename    = "/tmp/report.pdf",
        #     Bucket      = bucket,
        #     Key         = "reports/2024/report.pdf",
        #     ExtraArgs   = {
        #         "ContentType":   "application/pdf",
        #         "ServerSideEncryption": "AES256",   # encrypt at rest
        #         "Metadata":      {"user-id": "42", "report-type": "monthly"},
        #     }
        # )

        # Download file
        # s3.download_file(bucket, "reports/2024/report.pdf", "/tmp/downloaded.pdf")

        # List objects
        # response = s3.list_objects_v2(Bucket=bucket, Prefix="reports/", MaxKeys=100)
        # files = [obj["Key"] for obj in response.get("Contents", [])]

        # INTERVIEW: Presigned URL = temporary access without AWS credentials
        # User ko direct browser se S3 se download/upload karne dete hain
        # presigned_url = s3.generate_presigned_url(
        #     "get_object",
        #     Params     = {"Bucket": bucket, "Key": "reports/2024/report.pdf"},
        #     ExpiresIn  = 3600,   # 1 hour validity
        # )

        # Presigned POST for browser uploads
        # presigned_post = s3.generate_presigned_post(
        #     Bucket     = bucket,
        #     Key        = "uploads/${filename}",
        #     Fields     = {"Content-Type": "image/jpeg"},
        #     Conditions = [
        #         {"Content-Type": "image/jpeg"},
        #         ["content-length-range", 1, 5_000_000],  # max 5MB
        #     ],
        #     ExpiresIn  = 300,
        # )

        print("  S3 code patterns shown (set AWS env vars to run real calls)")

    except ImportError:
        print("  boto3 not installed: pip install boto3")
    except Exception as e:
        print(f"  AWS not configured: {type(e).__name__}")

    # Show S3 best practices
    print("\n  S3 Best Practices:")
    tips = {
        "Bucket policy":      "Block public access by default, use presigned URLs",
        "Versioning":         "Enable for accidental deletion protection",
        "Lifecycle rules":    "Move old objects to Glacier (cheaper storage)",
        "Transfer acceleration": "For global uploads (uses CloudFront)",
        "Multipart upload":   "For files > 100MB (parallel upload parts)",
        "Server-side encryption": "AES256 or KMS (regulatory compliance)",
    }
    for k, v in tips.items():
        print(f"    {k:<25}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: boto3 — SQS (Message Queue)
# INTERVIEW: Async processing, decoupling services
# ─────────────────────────────────────────────────────────────────────────────

def demo_sqs():
    """SQS: send and receive messages."""
    print("\n[SQS Demo]")

    SQS_PATTERNS = {
        "Standard Queue":  "At-least-once delivery, best-effort ordering",
        "FIFO Queue":      "Exactly-once delivery, strict ordering (.fifo suffix)",
        "DLQ":             "Dead Letter Queue — failed messages after max retries",
        "Visibility timeout": "Time worker has to process before message reappears",
        "Long polling":    "WaitTimeSeconds=20 → reduce empty receives + cost",
    }
    for pattern, desc in SQS_PATTERNS.items():
        print(f"  {pattern:<22}: {desc}")

    print("\n  SQS Code Pattern (requires AWS credentials):")
    sqs_code = """\
    import boto3
    import json

    sqs = boto3.client('sqs', region_name='us-east-1')
    QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123/my-queue'

    # Send message
    sqs.send_message(
        QueueUrl    = QUEUE_URL,
        MessageBody = json.dumps({'user_id': 42, 'action': 'send_email'}),
        MessageAttributes = {
            'action': {'StringValue': 'send_email', 'DataType': 'String'}
        }
    )

    # Receive + process + delete (at-least-once pattern)
    while True:
        response = sqs.receive_message(
            QueueUrl            = QUEUE_URL,
            MaxNumberOfMessages = 10,
            WaitTimeSeconds     = 20,   # long polling
            VisibilityTimeout   = 60,   # 60s to process
        )
        for msg in response.get('Messages', []):
            body = json.loads(msg['Body'])
            try:
                process_message(body)
                # CRITICAL: Delete after successful processing!
                sqs.delete_message(
                    QueueUrl      = QUEUE_URL,
                    ReceiptHandle = msg['ReceiptHandle']
                )
            except Exception:
                pass  # Message reappears after VisibilityTimeout
    """
    print(sqs_code)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Zero-Downtime Deployment Strategies
# INTERVIEW: Blue-Green, Rolling, Canary
# ─────────────────────────────────────────────────────────────────────────────

DEPLOYMENT_STRATEGIES = {
    "Rolling Deployment": {
        "description": "Gradually replace old instances with new ones",
        "pros":        ["No extra infrastructure cost", "Gradual rollout"],
        "cons":        ["Mixed versions running simultaneously", "Rollback is slow"],
        "use_when":    "Most production deployments (ECS default)",
    },
    "Blue-Green Deployment": {
        "description": "Two identical environments, switch traffic instantly",
        "pros":        ["Instant rollback (just switch back)", "Zero downtime"],
        "cons":        ["2x infrastructure cost during deployment"],
        "use_when":    "Critical deployments needing instant rollback",
    },
    "Canary Deployment": {
        "description": "Route small % of traffic to new version",
        "pros":        ["Test with real traffic", "Easy monitoring"],
        "cons":        ["Complex routing setup", "Long deployment time"],
        "use_when":    "High-risk changes (algorithm, pricing logic)",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("CI/CD + AWS PRACTICAL")
    print("=" * 60)

    print("\n[1] GitHub Actions CI Pipeline:")
    stages = ["lint → ruff + mypy", "test → pytest + coverage + services",
              "build-push → Docker → ECR", "deploy → ECS (needs approval)"]
    for i, s in enumerate(stages, 1):
        print(f"  Step {i}: {s}")

    print("\n[2] GitHub Actions Key Concepts:")
    concepts = {
        "OIDC auth":            "No long-lived AWS keys in GitHub secrets",
        "services:":            "Docker containers available during tests (postgres, redis)",
        "cache: hashFiles":     "Cache deps by lock file hash → faster CI",
        "concurrency:":         "Cancel old runs when new push arrives",
        "environment: prod":    "Requires manual approval gate in GitHub UI",
        "needs: lint":          "Only run test job if lint job passes",
    }
    for k, v in concepts.items():
        print(f"  {k:<28}: {v}")

    demo_s3()
    demo_sqs()

    print("\n[5] Deployment Strategies:")
    for strategy, info in DEPLOYMENT_STRATEGIES.items():
        print(f"\n  {strategy}:")
        print(f"    Description: {info['description']}")
        print(f"    Use when:    {info['use_when']}")

    print("\n" + "=" * 60)
    print("AWS INTERVIEW QUICK ANSWERS:")
    print("  Q: S3 presigned URL?")
    print("     Temporary access URL (no credentials needed). Expires in N seconds.")
    print("  Q: SQS FIFO vs Standard?")
    print("     FIFO: exactly-once, ordered, 3000 msg/s. Standard: at-least-once, 10x faster.")
    print("  Q: Blue-Green vs Canary?")
    print("     Blue-Green: instant switch. Canary: gradual %, monitors metrics.")
    print("  Q: How to avoid AWS keys in CI?")
    print("     OIDC: GitHub Actions gets temporary credentials via role assumption.")
    print("=" * 60)


if __name__ == "__main__":
    main()
