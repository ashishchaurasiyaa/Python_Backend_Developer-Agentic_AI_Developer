#!/usr/bin/env bash
# Self-checking verifier for Lab 5 -- `terraform import` adopting existing infra.
# PASS only if the bucket (created OUTSIDE Terraform, with a marker object
# inside it) ends up correctly tracked in Terraform state WITHOUT ever being
# destroyed and recreated (proven by the marker object surviving).
set -uo pipefail
cd "$(dirname "$0")"
SCRATCH=$(mktemp -d)
ENDPOINT=http://localhost:4566
BUCKET=tf-lab-imported-bucket
FAIL=0

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
# Without this, the AWS provider's custom-endpoint preflight retries for
# ~2 minutes against LocalStack before giving up and proceeding anyway --
# harmless but slow. This skips that probe entirely.
export AWS_EC2_METADATA_DISABLED=true

cleanup() {
  aws --endpoint-url="$ENDPOINT" s3 rm "s3://$BUCKET" --recursive >/dev/null 2>&1
  aws --endpoint-url="$ENDPOINT" s3 rb "s3://$BUCKET" >/dev/null 2>&1
  rm -rf "$SCRATCH"
}
trap cleanup EXIT

echo "==> checking LocalStack is up ($ENDPOINT)"
if ! curl -sf "$ENDPOINT/_localstack/health" >/dev/null 2>&1; then
  echo "FAIL: LocalStack isn't reachable at $ENDPOINT -- run '(cd ../_setup && docker compose up -d)' first"
  exit 1
fi
echo "    OK"

echo "==> [bootstrap] creating '$BUCKET' OUTSIDE Terraform, with a marker object inside"
aws --endpoint-url="$ENDPOINT" s3 mb "s3://$BUCKET" >/dev/null 2>&1
echo "pre-existing, do not lose me" > "$SCRATCH/marker.txt"
aws --endpoint-url="$ENDPOINT" s3 cp "$SCRATCH/marker.txt" "s3://$BUCKET/marker.txt" >/dev/null 2>&1
echo "    OK -- bucket + marker.txt exist, entirely outside Terraform's knowledge"

cp main.tf "$SCRATCH/main.tf"
cd "$SCRATCH"
terraform init -input=false >/dev/null 2>&1

echo "==> terraform apply (should import, not create-from-scratch)"
apply_output=$(terraform apply -auto-approve -input=false 2>&1)
echo "$apply_output" | tail -8

if echo "$apply_output" | grep -qi "BucketAlreadyExists"; then
  echo
  echo "FAIL: Terraform tried to CREATE the bucket and got BucketAlreadyExists."
  echo "      The TODO (the 'import' block) was never added -- Terraform had no idea"
  echo "      this bucket already existed."
  exit 1
fi

if echo "$apply_output" | grep -qiE "error"; then
  echo "FAIL: terraform apply errored for a reason other than BucketAlreadyExists -- see output above"
  exit 1
fi

echo "==> checking aws_s3_bucket.adopted is now tracked in Terraform state"
if terraform state list 2>/dev/null | grep -q "aws_s3_bucket.adopted"; then
  echo "    OK -- resource is in state"
else
  echo "FAIL: aws_s3_bucket.adopted is not in 'terraform state list'"
  FAIL=1
fi

echo "==> confirming the marker object SURVIVED (proves no destroy/recreate happened)"
if aws --endpoint-url="$ENDPOINT" s3 ls "s3://$BUCKET/marker.txt" >/dev/null 2>&1; then
  echo "    OK -- marker.txt still exists in the bucket"
else
  echo "FAIL: marker.txt is gone -- the bucket was destroyed and recreated at some point"
  FAIL=1
fi

echo "==> confirming 'terraform plan' now shows no further changes (config matches reality)"
plan_summary=$(terraform plan -input=false -no-color 2>&1 | grep -E "No changes|Plan:" || true)
echo "    plan says: ${plan_summary:-'(nothing matched)'}"
if echo "$plan_summary" | grep -q "No changes"; then
  echo "    OK"
else
  echo "FAIL: terraform plan still wants to change something -- config doesn't fully match the imported reality"
  FAIL=1
fi

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS -- pre-existing bucket adopted into Terraform state, marker.txt untouched throughout."
  exit 0
else
  echo
  echo "RESULT: FAIL -- see messages above."
  exit 1
fi
