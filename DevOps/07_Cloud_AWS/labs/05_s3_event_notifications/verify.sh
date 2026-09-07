#!/usr/bin/env bash
# Self-checking verifier for Lab 5 -- S3 event notifications -> SQS.
# PASS only if uploading an object actually produces a real ObjectCreated
# event in the queue (not just the automatic s3:TestEvent that fires when
# notifications are first configured).
set -uo pipefail
cd "$(dirname "$0")"
ENDPOINT=http://localhost:4566
FAIL=0

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

cleanup() {
  aws --endpoint-url="$ENDPOINT" s3 rm s3://lab5-bucket --recursive >/dev/null 2>&1
  aws --endpoint-url="$ENDPOINT" s3 rb s3://lab5-bucket >/dev/null 2>&1
  url=$(aws --endpoint-url="$ENDPOINT" sqs get-queue-url --queue-name lab5-queue --query QueueUrl --output text 2>/dev/null)
  [ -n "$url" ] && [ "$url" != "None" ] && aws --endpoint-url="$ENDPOINT" sqs delete-queue --queue-url "$url" >/dev/null 2>&1
}
trap cleanup EXIT

echo "==> checking LocalStack is up ($ENDPOINT)"
if ! curl -sf "$ENDPOINT/_localstack/health" >/dev/null 2>&1; then
  echo "FAIL: LocalStack isn't reachable at $ENDPOINT -- run '(cd ../_setup && docker compose up -d)' first"
  exit 1
fi
echo "    OK"

cleanup  # in case a previous run left resources behind

echo "==> running lab.py (creates bucket+queue, uploads one object)"
output=$(AWS_ENDPOINT_URL="$ENDPOINT" python3 lab.py 2>&1)
echo "$output"

real_events=$(echo "$output" | grep -oE "real ObjectCreated events received: [0-9]+" | grep -oE "[0-9]+")

if [ "$real_events" = "1" ]; then
  echo "    OK -- exactly 1 real ObjectCreated event reached the queue"
elif [ "$real_events" = "0" ]; then
  echo "FAIL: 0 ObjectCreated events reached the queue."
  echo "      Most likely cause: no bucket notification configuration was set (TODO not done)."
  FAIL=1
else
  echo "FAIL: expected 1 event, got '$real_events' -- check lab.py ran without errors above"
  FAIL=1
fi

if echo "$output" | grep -q "key: hello.txt"; then
  echo "    OK -- the event correctly identifies the uploaded key (hello.txt)"
else
  if [ "$real_events" = "1" ]; then
    echo "FAIL: got an ObjectCreated event but it doesn't reference hello.txt -- unexpected"
    FAIL=1
  fi
fi

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS -- uploading to the bucket produced a real, correctly-identified event in the queue."
  exit 0
else
  echo
  echo "RESULT: FAIL -- see messages above."
  exit 1
fi
