#!/usr/bin/env bash
# Self-checking verifier for Lab 4 -- read-only rootfs + tmpfs scratch space.
# PASS only if writes OUTSIDE /tmp fail (always, by design) AND writes
# INSIDE /tmp succeed (only once the tmpfs mount is added).
set -uo pipefail
cd "$(dirname "$0")"
FAIL=0

cleanup() {
  docker compose down >/dev/null 2>&1
}
trap cleanup EXIT

echo "==> docker compose up -d"
docker compose up -d >/dev/null 2>&1
sleep 1

echo "==> checking: can it write OUTSIDE /tmp (e.g. /app) ?"
write_root=$(docker compose exec -T app sh -c 'touch /app-testfile 2>&1; echo EXIT:$?')
echo "    $write_root"

echo "==> checking: can it write INSIDE /tmp ?"
write_tmp=$(docker compose exec -T app sh -c 'touch /tmp/testfile 2>&1; echo EXIT:$?')
echo "    $write_tmp"

if echo "$write_root" | grep -q "EXIT:0"; then
  echo "FAIL: writing outside /tmp succeeded -- read_only: true isn't actually in effect."
  FAIL=1
else
  echo "    OK -- writing outside /tmp was denied (read-only root, as intended)"
fi

if echo "$write_tmp" | grep -q "EXIT:0"; then
  echo "    OK -- writing to /tmp succeeded (tmpfs mount is working)"
else
  echo "FAIL: writing to /tmp failed too -- the whole filesystem is read-only with no scratch space."
  echo "      Most likely cause: the tmpfs mount for /tmp was never added (TODO not done)."
  FAIL=1
fi

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS -- root filesystem locked down, /tmp still usable as scratch space."
  exit 0
else
  echo
  echo "RESULT: FAIL -- see messages above."
  exit 1
fi
