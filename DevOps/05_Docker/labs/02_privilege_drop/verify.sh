#!/usr/bin/env bash
# Self-checking verifier for Lab 2 -- non-root privilege enforcement.
# PASS only if the container's default user can NOT write to /root and can
# NOT install a system package (apk needs to write to a root-owned DB) --
# while it CAN still write to its own /app.
#
# NOTE: an earlier version of this lab also tested binding to port 80 as a
# "root-only" privilege. That check was DROPPED after live-testing revealed
# it's not portable: this host's kernel has
# net.ipv4.ip_unprivileged_port_start=0, meaning ANY user (root or not) can
# bind ANY port here -- a per-host/per-kernel sysctl, not something Docker
# itself enforces. File permissions and package-manager writes below don't
# have that problem; they're real UNIX permission bits, consistent everywhere.
set -uo pipefail
cd "$(dirname "$0")"
IMAGE=lab2-privilege-drop
FAIL=0

cleanup() {
  docker rmi -f "$IMAGE" >/dev/null 2>&1
}
trap cleanup EXIT

echo "==> building"
if ! docker build -t "$IMAGE" . >/tmp/lab2_build.log 2>&1; then
  echo "FAIL: docker build failed -- see /tmp/lab2_build.log"
  exit 1
fi

echo "==> checking the effective user"
whoami_out=$(docker run --rm "$IMAGE" whoami 2>&1)
echo "    container runs as: $whoami_out"

echo "==> checking: can it write to /root ?"
write_root=$(docker run --rm "$IMAGE" sh -c 'touch /root/testfile 2>&1; echo EXIT:$?')
echo "    $write_root"

echo "==> checking: can it still write to its OWN /app ?"
write_app=$(docker run --rm "$IMAGE" sh -c 'touch /app/testfile 2>&1; echo EXIT:$?')
echo "    $write_app"

echo "==> checking: can it install a system package (apk needs root-owned db access) ?"
apk_result=$(docker run --rm "$IMAGE" sh -c 'apk add --no-cache curl >/dev/null 2>&1; echo EXIT:$?')
echo "    $apk_result"

if [ "$whoami_out" = "root" ]; then
  echo "FAIL: container is still running as root -- the TODO (USER appuser) was never added."
  FAIL=1
else
  echo "    OK -- running as '$whoami_out', not root"
fi

if echo "$write_root" | grep -q "EXIT:0"; then
  echo "FAIL: writing to /root succeeded -- that should only be possible as root."
  FAIL=1
else
  echo "    OK -- writing to /root was denied"
fi

if echo "$write_app" | grep -q "EXIT:0"; then
  echo "    OK -- writing to /app (its own directory) succeeded, as expected"
else
  echo "FAIL: writing to /app failed -- the non-root user doesn't even own its own working directory (chown missing?)"
  FAIL=1
fi

if echo "$apk_result" | grep -q "EXIT:0"; then
  echo "FAIL: installing a system package succeeded -- that should require root."
  FAIL=1
else
  echo "    OK -- installing a system package was denied (needs root-owned apk db)"
fi

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS -- non-root user can work in its own directory but can't touch root-owned paths or install packages."
  exit 0
else
  echo
  echo "RESULT: FAIL -- see messages above."
  exit 1
fi
