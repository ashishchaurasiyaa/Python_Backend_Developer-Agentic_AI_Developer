#!/usr/bin/env bash
# Self-checking verifier for Lab 1 -- build secrets vs leaked ARGs.
# PASS only if the secret string does NOT appear anywhere in `docker history`,
# even though the SAME secret is supplied both ways (as --build-arg, in case
# the Dockerfile still uses ARG, and as --secret, in case it's been fixed).
set -uo pipefail
cd "$(dirname "$0")"
IMAGE=lab1-build-secrets
SECRET_VALUE="SUPERSECRET-token-a1b2c3"
FAIL=0

cleanup() {
  docker rmi -f "$IMAGE" >/dev/null 2>&1
  rm -f secret.txt
}
trap cleanup EXIT

echo "$SECRET_VALUE" > secret.txt

echo "==> building (supplying the secret BOTH ways -- whichever the Dockerfile actually uses will pick it up)"
if ! DOCKER_BUILDKIT=1 docker build \
  --build-arg SECRET_TOKEN="$SECRET_VALUE" \
  --secret id=token,src=secret.txt \
  -t "$IMAGE" . >/tmp/lab1_build.log 2>&1; then
  echo "FAIL: docker build itself failed -- see /tmp/lab1_build.log"
  cat /tmp/lab1_build.log | tail -20
  exit 1
fi
echo "    OK -- image built"

echo "==> checking 'docker history --no-trunc' for the leaked secret"
history_output=$(docker history --no-trunc "$IMAGE" 2>&1)

if echo "$history_output" | grep -q "$SECRET_VALUE"; then
  echo "FAIL: the secret value IS visible in 'docker history' -- anyone with this image can read it out."
  echo "      Most likely cause: the Dockerfile still uses ARG SECRET_TOKEN (TODO not done)."
  echo "      Leaked line:"
  echo "$history_output" | grep "$SECRET_VALUE" | sed 's/^/        /'
  FAIL=1
else
  echo "    OK -- secret does NOT appear anywhere in image history"
fi

echo "==> double-checking by inspecting the raw image config + layers too"
docker save "$IMAGE" -o /tmp/lab1_image.tar 2>/dev/null
if tar -xOf /tmp/lab1_image.tar 2>/dev/null | grep -a -q "$SECRET_VALUE"; then
  echo "FAIL: the secret is embedded somewhere in the saved image tarball itself (a layer or config), not just history."
  FAIL=1
else
  echo "    OK -- secret not found anywhere in the exported image tarball either"
fi
rm -f /tmp/lab1_image.tar /tmp/lab1_build.log

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS -- the secret was used during the build but leaves zero trace in the resulting image."
  exit 0
else
  echo
  echo "RESULT: FAIL -- see messages above."
  exit 1
fi
