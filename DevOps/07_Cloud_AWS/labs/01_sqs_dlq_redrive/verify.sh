#!/usr/bin/env bash
# Self-checking verifier for Lab 1 -- SQS DLQ redrive.
# PASS only if the poison message actually ends up in the DLQ after 3
# failed receives, not looping in the main queue forever.
set -uo pipefail
cd "$(dirname "$0")"
ENDPOINT=http://localhost:4566
FAIL=0

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

cleanup() {
  for q in lab1-main lab1-dlq; do
    url=$(aws --endpoint-url="$ENDPOINT" sqs get-queue-url --queue-name "$q" --query QueueUrl --output text 2>/dev/null)
    [ -n "$url" ] && [ "$url" != "None" ] && aws --endpoint-url="$ENDPOINT" sqs delete-queue --queue-url "$url" >/dev/null 2>&1
  done
}
trap cleanup EXIT

echo "==> checking LocalStack is up ($ENDPOINT)"
if ! curl -sf "$ENDPOINT/_localstack/health" >/dev/null 2>&1; then
  echo "FAIL: LocalStack isn't reachable at $ENDPOINT -- run '(cd ../_setup && docker compose up -d)' first"
  exit 1
fi
echo "    OK"

cleanup  # in case a previous run left queues behind

echo "==> running lab.py (creates queues, simulates a message failing 5 times)"
AWS_ENDPOINT_URL="$ENDPOINT" python3 lab.py 2>&1 | tee /tmp/lab1_run.log

dlq_url=$(aws --endpoint-url="$ENDPOINT" sqs get-queue-url --queue-name lab1-dlq --query QueueUrl --output text 2>/dev/null)
if [ -z "$dlq_url" ] || [ "$dlq_url" = "None" ]; then
  echo "FAIL: the DLQ doesn't even exist -- lab.py may have errored, check the log above"
  exit 1
fi

echo "==> independently checking (via aws cli, not trusting lab.py's own print) how many messages are in the DLQ"
dlq_count=$(aws --endpoint-url="$ENDPOINT" sqs get-queue-attributes \
  --queue-url "$dlq_url" --attribute-names ApproximateNumberOfMessages \
  --query 'Attributes.ApproximateNumberOfMessages' --output text)
echo "    DLQ message count: $dlq_count"

if [ "$dlq_count" = "1" ]; then
  echo "    OK -- exactly 1 message redirected to the DLQ after failing 3 times"
else
  echo "FAIL: expected exactly 1 message in the DLQ, found $dlq_count."
  echo "      Most likely cause: no RedrivePolicy was set on the main queue (TODO not done),"
  echo "      so the message just keeps looping in the main queue and never reaches the DLQ."
  FAIL=1
fi

rm -f /tmp/lab1_run.log

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS -- a message that failed 3 times was correctly redirected to the DLQ, not left looping forever."
  exit 0
else
  echo
  echo "RESULT: FAIL -- see messages above."
  exit 1
fi
