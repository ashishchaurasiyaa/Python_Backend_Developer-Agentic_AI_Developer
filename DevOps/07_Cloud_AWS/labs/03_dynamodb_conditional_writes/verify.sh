#!/usr/bin/env bash
# Self-checking verifier for Lab 3 -- DynamoDB conditional writes vs lost updates.
# PASS only if the stale writer's update is REJECTED (final balance=150,
# A's change preserved) rather than silently overwriting A's write (130).
set -uo pipefail
cd "$(dirname "$0")"
ENDPOINT=http://localhost:4566
FAIL=0

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

cleanup() {
  aws --endpoint-url="$ENDPOINT" dynamodb delete-table --table-name lab3-accounts >/dev/null 2>&1
}
trap cleanup EXIT

echo "==> checking LocalStack is up ($ENDPOINT)"
if ! curl -sf "$ENDPOINT/_localstack/health" >/dev/null 2>&1; then
  echo "FAIL: LocalStack isn't reachable at $ENDPOINT -- run '(cd ../_setup && docker compose up -d)' first"
  exit 1
fi
echo "    OK"

cleanup  # in case a previous run left the table behind

echo "==> running lab.py (A and B both read balance=100/version=1, then write conflicting updates)"
output=$(AWS_ENDPOINT_URL="$ENDPOINT" python3 lab.py 2>&1)
echo "$output"

echo "==> independently checking the final balance (via aws cli, not trusting lab.py's own print)"
final_balance=$(aws --endpoint-url="$ENDPOINT" dynamodb get-item \
  --table-name lab3-accounts --key '{"account_id":{"S":"acc1"}}' \
  --query 'Item.balance.N' --output text)
echo "    final balance in the table: $final_balance"

if [ "$final_balance" = "150" ]; then
  echo "    OK -- balance is 150 (A's write preserved, B's stale write correctly rejected)"
elif [ "$final_balance" = "130" ]; then
  echo "FAIL: balance is 130 -- B's stale write silently overwrote A's change (the lost-update bug)."
  echo "      Most likely cause: no ConditionExpression was added to apply_delta() (TODO not done)."
  FAIL=1
else
  echo "FAIL: unexpected final balance '$final_balance' -- check lab.py ran without errors above"
  FAIL=1
fi

if echo "$output" | grep -q "ConditionalCheckFailedException"; then
  if [ "$final_balance" != "150" ]; then
    echo "FAIL: saw a ConditionalCheckFailedException but the final balance wasn't 150 -- inconsistent result"
    FAIL=1
  fi
else
  if [ "$final_balance" = "150" ]; then
    echo "FAIL: balance is 150 but no ConditionalCheckFailedException was ever raised -- inconsistent result"
    FAIL=1
  fi
fi

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS -- B's stale write was rejected instead of silently corrupting A's update."
  exit 0
else
  echo
  echo "RESULT: FAIL -- see messages above."
  exit 1
fi
