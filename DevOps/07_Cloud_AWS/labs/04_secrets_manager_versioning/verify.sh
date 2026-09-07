#!/usr/bin/env bash
# Self-checking verifier for Lab 4 -- Secrets Manager AWSCURRENT/AWSPREVIOUS.
# PASS only if requesting AWSPREVIOUS actually returns the OLD value, not
# silently the current one.
set -uo pipefail
cd "$(dirname "$0")"
ENDPOINT=http://localhost:4566
FAIL=0

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

cleanup() {
  aws --endpoint-url="$ENDPOINT" secretsmanager delete-secret \
    --secret-id lab4/db-password --force-delete-without-recovery >/dev/null 2>&1
}
trap cleanup EXIT

echo "==> checking LocalStack is up ($ENDPOINT)"
if ! curl -sf "$ENDPOINT/_localstack/health" >/dev/null 2>&1; then
  echo "FAIL: LocalStack isn't reachable at $ENDPOINT -- run '(cd ../_setup && docker compose up -d)' first"
  exit 1
fi
echo "    OK"

cleanup  # in case a previous run left the secret behind

echo "==> running lab.py (creates secret, rotates it, fetches both stages)"
output=$(AWS_ENDPOINT_URL="$ENDPOINT" python3 lab.py 2>&1)
echo "$output"

echo "==> independently checking both version stages (via aws cli, not trusting lab.py's own print)"
current_val=$(aws --endpoint-url="$ENDPOINT" secretsmanager get-secret-value \
  --secret-id lab4/db-password --version-stage AWSCURRENT --query SecretString --output text)
previous_val=$(aws --endpoint-url="$ENDPOINT" secretsmanager get-secret-value \
  --secret-id lab4/db-password --version-stage AWSPREVIOUS --query SecretString --output text)
echo "    AWSCURRENT (ground truth)  = $current_val"
echo "    AWSPREVIOUS (ground truth) = $previous_val"

reported_current=$(echo "$output" | grep -oE "requested AWSCURRENT.*got '[^']*'" | grep -oE "'[^']*'" | tr -d "'")
reported_previous=$(echo "$output" | grep -oE "requested AWSPREVIOUS.*got '[^']*'" | grep -oE "'[^']*'" | tr -d "'")

if [ "$reported_previous" = "$previous_val" ] && [ "$previous_val" = "password-v1" ]; then
  echo "    OK -- get_secret(stage=AWSPREVIOUS) correctly returned the OLD value ('password-v1')"
else
  echo "FAIL: get_secret(stage=AWSPREVIOUS) returned '$reported_previous', expected 'password-v1'."
  echo "      Most likely cause: get_secret() never passes VersionStage through to the API call (TODO not done)."
  FAIL=1
fi

if [ "$reported_current" = "$current_val" ] && [ "$current_val" = "password-v2" ]; then
  echo "    OK -- get_secret(stage=AWSCURRENT) correctly returned the NEW value ('password-v2')"
else
  echo "FAIL: get_secret(stage=AWSCURRENT) returned '$reported_current', expected 'password-v2'."
  FAIL=1
fi

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS -- AWSCURRENT and AWSPREVIOUS both resolve to their correct, distinct values."
  exit 0
else
  echo
  echo "RESULT: FAIL -- see messages above."
  exit 1
fi
