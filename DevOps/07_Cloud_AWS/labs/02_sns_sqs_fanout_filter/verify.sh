#!/usr/bin/env bash
# Self-checking verifier for Lab 2 -- SNS -> SQS fan-out with a filter policy.
# PASS only if exactly the 2 priority=urgent messages reach the queue, not
# all 3 published.
set -uo pipefail
cd "$(dirname "$0")"
ENDPOINT=http://localhost:4566
FAIL=0

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

cleanup() {
  aws --endpoint-url="$ENDPOINT" sns list-topics --query 'Topics[].TopicArn' --output text 2>/dev/null \
    | tr '\t' '\n' | grep lab2-topic | xargs -I{} aws --endpoint-url="$ENDPOINT" sns delete-topic --topic-arn {} >/dev/null 2>&1
  url=$(aws --endpoint-url="$ENDPOINT" sqs get-queue-url --queue-name lab2-queue --query QueueUrl --output text 2>/dev/null)
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

echo "==> running lab.py (creates topic+queue, subscribes, publishes 3 messages: 2 urgent, 1 low)"
output=$(AWS_ENDPOINT_URL="$ENDPOINT" python3 lab.py 2>&1)
echo "$output"

received_count=$(echo "$output" | grep -oE "messages that reached the queue: [0-9]+" | grep -oE "[0-9]+")

if [ "$received_count" = "2" ]; then
  echo "    OK -- exactly 2 messages reached the queue (the 2 priority=urgent ones)"
elif [ "$received_count" = "3" ]; then
  echo "FAIL: all 3 messages reached the queue, including the priority=low one."
  echo "      Most likely cause: no FilterPolicy was set on the subscription (TODO not done)."
  FAIL=1
else
  echo "FAIL: expected 2 or 3 messages, got '$received_count' -- check lab.py ran without errors above"
  FAIL=1
fi

received_section=$(echo "$output" | sed -n '/messages that reached the queue/,$p')
if echo "$received_section" | grep -q "order #2 created"; then
  echo "FAIL: the priority=low message ('order #2 created') is among the RECEIVED messages -- the filter let it through."
  FAIL=1
fi

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS -- the filter policy correctly kept the priority=low message out of the queue."
  exit 0
else
  echo
  echo "RESULT: FAIL -- see messages above."
  exit 1
fi
