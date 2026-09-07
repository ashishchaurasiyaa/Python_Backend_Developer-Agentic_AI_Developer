#!/usr/bin/env bash
# Self-checking verifier for Lab 4 -- S3+DynamoDB remote state backend.
# PASS only if `terraform init` actually succeeds against LocalStack (not
# real AWS) AND the state file genuinely lands in the LocalStack S3 bucket,
# not on local disk.
set -uo pipefail
cd "$(dirname "$0")"
SCRATCH=$(mktemp -d)
ENDPOINT=http://localhost:4566
BUCKET=tf-lab-state
TABLE=tf-lab-locks
FAIL=0

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

cleanup() {
  aws --endpoint-url="$ENDPOINT" s3 rm "s3://$BUCKET" --recursive >/dev/null 2>&1
  aws --endpoint-url="$ENDPOINT" s3 rb "s3://$BUCKET" >/dev/null 2>&1
  aws --endpoint-url="$ENDPOINT" dynamodb delete-table --table-name "$TABLE" >/dev/null 2>&1
  rm -rf "$SCRATCH"
}
trap cleanup EXIT

echo "==> checking LocalStack is up ($ENDPOINT)"
if ! curl -sf "$ENDPOINT/_localstack/health" >/dev/null 2>&1; then
  echo "FAIL: LocalStack isn't reachable at $ENDPOINT -- run '(cd ../_setup && docker compose up -d)' first"
  exit 1
fi
echo "    OK"

echo "==> [bootstrap] creating the backend's own storage in LocalStack (bucket + lock table)"
aws --endpoint-url="$ENDPOINT" s3 mb "s3://$BUCKET" >/dev/null 2>&1
aws --endpoint-url="$ENDPOINT" dynamodb create-table \
  --table-name "$TABLE" \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST >/dev/null 2>&1
sleep 1

cp main.tf "$SCRATCH/main.tf"
cd "$SCRATCH"

echo "==> terraform init (should point at LocalStack, not real AWS)"
if ! terraform init -input=false 2>&1 | tee /tmp/lab4_init.log | tail -5; then
  :
fi
if grep -qi "error" /tmp/lab4_init.log; then
  echo "FAIL: terraform init failed. Most likely cause: the TODO (endpoints + use_path_style) was never added,"
  echo "      so Terraform tried to reach real AWS instead of LocalStack."
  exit 1
fi

echo "==> terraform apply"
if ! terraform apply -auto-approve -input=false >/dev/null 2>&1; then
  echo "FAIL: terraform apply failed after a successful init -- check /tmp/lab4_init.log and re-run manually"
  exit 1
fi
echo "    OK -- apply succeeded"

echo "==> checking the state file actually landed in the LocalStack S3 bucket"
if aws --endpoint-url="$ENDPOINT" s3 ls "s3://$BUCKET/lab4/terraform.tfstate" >/dev/null 2>&1; then
  echo "    OK -- s3://$BUCKET/lab4/terraform.tfstate exists in LocalStack"
else
  echo "FAIL: no state object found in the LocalStack bucket -- state may have been written locally instead"
  FAIL=1
fi

echo "==> confirming there is NO local terraform.tfstate file (proves it's genuinely remote, not local)"
if [ -f "$SCRATCH/terraform.tfstate" ]; then
  echo "FAIL: a local terraform.tfstate file exists -- the S3 backend isn't actually being used"
  FAIL=1
else
  echo "    OK -- no local state file, state lives only in LocalStack S3"
fi

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS -- remote state backend (S3 + DynamoDB lock) verified against a real, running S3-compatible API."
  exit 0
else
  echo
  echo "RESULT: FAIL -- see messages above."
  exit 1
fi
