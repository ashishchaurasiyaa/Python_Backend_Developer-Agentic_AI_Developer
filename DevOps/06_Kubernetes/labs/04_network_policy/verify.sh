#!/usr/bin/env bash
# Self-checking verifier for Lab 4 — NetworkPolicy default-deny + selective allow.
# PASS only if a Pod labeled role=allowed CAN reach the web Service, AND a
# Pod with no such label CANNOT.
set -uo pipefail
cd "$(dirname "$0")"
NS=k8s-labs
FAIL=0

cleanup() {
  kubectl delete pod allowed-client blocked-client -n "$NS" --ignore-not-found >/dev/null 2>&1
  kubectl delete -f manifest.yaml -n "$NS" --ignore-not-found >/dev/null 2>&1
}
trap cleanup EXIT

echo "==> applying manifest.yaml"
kubectl apply -f manifest.yaml -n "$NS" >/dev/null

echo "==> waiting up to 60s for the web Deployment"
if ! kubectl wait --for=condition=Available deployment/web -n "$NS" --timeout=60s >/dev/null 2>&1; then
  echo "FAIL: web Deployment never became Available"
  exit 1
fi

echo "==> giving Calico a moment to program the policy"
sleep 3

echo "==> testing an ALLOWED client (label role=allowed) -- should succeed"
kubectl run allowed-client --image=curlimages/curl -n "$NS" --restart=Never \
  --labels=role=allowed --command -- sh -c \
  "curl -s -m 4 -o /dev/null -w 'HTTP %{http_code}\n' http://web.${NS}.svc.cluster.local || echo BLOCKED" >/dev/null
kubectl wait --for=condition=Ready pod/allowed-client -n "$NS" --timeout=30s >/dev/null 2>&1 || true
sleep 5
allowed_out=$(kubectl logs allowed-client -n "$NS" 2>/dev/null)
echo "    allowed-client output: $allowed_out"

echo "==> testing a BLOCKED client (no role label) -- should fail/timeout"
kubectl run blocked-client --image=curlimages/curl -n "$NS" --restart=Never \
  --command -- sh -c \
  "curl -s -m 4 -o /dev/null -w 'HTTP %{http_code}\n' http://web.${NS}.svc.cluster.local || echo BLOCKED" >/dev/null
kubectl wait --for=condition=Ready pod/blocked-client -n "$NS" --timeout=30s >/dev/null 2>&1 || true
sleep 5
blocked_out=$(kubectl logs blocked-client -n "$NS" 2>/dev/null)
echo "    blocked-client output: $blocked_out"

if echo "$allowed_out" | grep -q "HTTP 200"; then
  echo "    OK — allowed-client (role=allowed) reached the Service"
else
  echo "FAIL: allowed-client could NOT reach the Service. If blocked-client also failed below,"
  echo "      the TODO (adding the allow rule) was never done -- ingress: [] denies everyone, no exceptions."
  FAIL=1
fi

if echo "$blocked_out" | grep -qE "BLOCKED|HTTP 000"; then
  echo "    OK — blocked-client (no role label) could NOT reach the Service, as expected"
else
  echo "FAIL: blocked-client reached the Service ($blocked_out) -- the NetworkPolicy isn't restricting by label at all."
  FAIL=1
fi

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS — selective allow verified: role=allowed gets through, everyone else stays denied."
  exit 0
else
  echo
  echo "RESULT: FAIL — see messages above."
  exit 1
fi
