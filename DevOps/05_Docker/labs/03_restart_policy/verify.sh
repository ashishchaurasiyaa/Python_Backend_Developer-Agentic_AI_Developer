#!/usr/bin/env bash
# Self-checking verifier for Lab 3 -- restart policy semantics.
# PASS only if the container retries up to 3 times and then genuinely
# STOPS (RestartCount stabilizes at 3, doesn't keep climbing).
set -uo pipefail
cd "$(dirname "$0")"
FAIL=0

cleanup() {
  docker compose down >/dev/null 2>&1
}
trap cleanup EXIT

echo "==> docker compose up -d"
docker compose up -d >/dev/null 2>&1

echo "==> polling RestartCount over 20s to see where it stabilizes"
prev=-1
stable_since=0
final_count=0
for i in $(seq 1 20); do
  sleep 1
  cid=$(docker compose ps -aq flaky 2>/dev/null)
  count=$(docker inspect --format='{{.RestartCount}}' "$cid" 2>/dev/null)
  status=$(docker inspect --format='{{.State.Status}}' "$cid" 2>/dev/null)
  final_count="$count"

  if [ "$count" = "$prev" ]; then
    stable_since=$((stable_since + 1))
  else
    stable_since=0
  fi
  prev="$count"

  # once it's held the same count for 4 consecutive seconds, consider it settled
  if [ "$stable_since" -ge 4 ]; then
    echo "    settled at RestartCount=$count (status=$status) after ${i}s"
    break
  fi
done

echo "    final RestartCount=$final_count, status=$status"

if [ "$final_count" = "0" ]; then
  echo "FAIL: RestartCount stayed at 0 -- the container never retried at all."
  echo "      Most likely cause: restart is still \"no\" (TODO not done)."
  FAIL=1
elif [ "$final_count" = "3" ]; then
  echo "    OK -- restarted exactly 3 times, matching on-failure:3"
else
  echo "FAIL: RestartCount settled at $final_count, expected exactly 3 -- check the policy value you set."
  FAIL=1
fi

if [ "$status" != "exited" ]; then
  echo "FAIL: expected the container to end up Exited (given up), but status is '$status'"
  FAIL=1
else
  echo "    OK -- final status is 'exited', Docker genuinely gave up instead of looping forever"
fi

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS -- retried 3 times, then stopped for good. Not zero retries, not infinite retries."
  exit 0
else
  echo
  echo "RESULT: FAIL -- see messages above."
  exit 1
fi
