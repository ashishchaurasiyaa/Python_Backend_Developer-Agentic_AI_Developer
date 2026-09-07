#!/usr/bin/env bash
# Self-checking verifier for Lab 5 -- BuildKit cache mounts for pip.
# PASS only if, after requirements.txt changes (busting the layer cache),
# pip's OWN log shows "Using cached" instead of "Downloading" -- proof the
# BuildKit cache mount actually persisted pip's download cache across two
# separate `docker build` invocations.
set -uo pipefail
cd "$(dirname "$0")"
IMAGE=lab5-cache-mount
FAIL=0

cleanup() {
  docker rmi -f "$IMAGE" >/dev/null 2>&1
  # Also clear this lab's own BuildKit cache mount between runs, so
  # re-running verify.sh (e.g. stub -> solution) doesn't get a false PASS
  # from a PREVIOUS run's cache still being warm.
  docker builder prune --filter type=exec.cachemount --force >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "requests==2.31.0" > requirements.txt

echo "==> build 1 (cold -- pip has never seen this package before in this cache)"
DOCKER_BUILDKIT=1 docker build --progress=plain -t "$IMAGE" . >/tmp/lab5_build1.log 2>&1
if grep -q "Downloading requests" /tmp/lab5_build1.log; then
  echo "    OK -- build 1 downloaded requests from PyPI, as expected on a cold cache"
else
  echo "    NOTE: couldn't confirm a fresh download in build 1's log (may already be warm from a prior run)"
fi

echo "==> changing requirements.txt (busts the Docker LAYER cache, same package though)"
{
  echo "# a comment, to force the COPY+RUN layer to re-run"
  echo "requests==2.31.0"
} > requirements.txt

echo "==> build 2 (layer cache invalidated -- does pip re-download, or hit its own cache?)"
DOCKER_BUILDKIT=1 docker build --progress=plain -t "$IMAGE" . >/tmp/lab5_build2.log 2>&1

if grep -q "Using cached requests" /tmp/lab5_build2.log; then
  echo "    OK -- build 2's pip output says 'Using cached requests...' -- the cache mount worked"
elif grep -q "Downloading requests" /tmp/lab5_build2.log; then
  echo "FAIL: build 2 re-DOWNLOADED requests from PyPI even though nothing about the package changed."
  echo "      Most likely cause: no --mount=type=cache on the pip install RUN step (TODO not done)."
  FAIL=1
else
  echo "FAIL: could not find either 'Downloading' or 'Using cached' in build 2's log -- see /tmp/lab5_build2.log"
  FAIL=1
fi

rm -f requirements.txt
rm -f /tmp/lab5_build1.log /tmp/lab5_build2.log

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS -- pip's own download cache survived across two separate 'docker build' invocations."
  exit 0
else
  echo
  echo "RESULT: FAIL -- see messages above."
  exit 1
fi
