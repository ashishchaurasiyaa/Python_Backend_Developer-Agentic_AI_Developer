#!/usr/bin/env bash
# Self-checking verifier for Lab 2 — ConfigMap volume hot-reload vs env staleness.
# PASS only if: (a) the mounted file exists and matches the ConfigMap, (b)
# after the ConfigMap changes, the FILE eventually updates on its own, and
# (c) the ENV VAR does NOT update, ever, without a restart.
set -uo pipefail
cd "$(dirname "$0")"
NS=k8s-labs
FAIL=0

cleanup() {
  kubectl delete -f manifest.yaml -n "$NS" --ignore-not-found >/dev/null 2>&1
}
trap cleanup EXIT

echo "==> applying manifest.yaml (ConfigMap MESSAGE=v1)"
kubectl apply -f manifest.yaml -n "$NS" >/dev/null
kubectl wait --for=condition=Ready pod/config-test -n "$NS" --timeout=60s >/dev/null 2>&1 || {
  echo "FAIL: pod/config-test never became Ready — check 'kubectl describe pod/config-test -n $NS'"
  exit 1
}

echo "==> checking env var MESSAGE_ENV"
env_val=$(kubectl exec config-test -n "$NS" -- printenv MESSAGE_ENV 2>/dev/null)
if [ "$env_val" != "v1" ]; then
  echo "FAIL: expected env MESSAGE_ENV=v1, got '$env_val'"
  exit 1
fi
echo "    OK — MESSAGE_ENV=v1"

echo "==> checking mounted file /etc/config/MESSAGE"
file_val=$(kubectl exec config-test -n "$NS" -- cat /etc/config/MESSAGE 2>/dev/null)
if [ "$file_val" != "v1" ]; then
  echo "FAIL: expected /etc/config/MESSAGE to contain 'v1', got '$file_val' (empty likely means the TODO volumeMount was never added)"
  exit 1
fi
echo "    OK — /etc/config/MESSAGE=v1"

echo "==> updating the ConfigMap to MESSAGE=v2 (Pod is NOT touched)"
kubectl patch configmap app-config -n "$NS" --type merge -p '{"data":{"MESSAGE":"v2"}}' >/dev/null

echo "==> polling up to 120s for the MOUNTED FILE to pick up v2 (kubelet's periodic re-sync, not instant)"
file_ok=0
for i in $(seq 1 24); do
  file_val=$(kubectl exec config-test -n "$NS" -- cat /etc/config/MESSAGE 2>/dev/null)
  if [ "$file_val" = "v2" ]; then file_ok=1; break; fi
  sleep 5
done

if [ "$file_ok" = "1" ]; then
  echo "    OK — /etc/config/MESSAGE became v2 after ~$((i*5))s, with ZERO Pod restarts, ZERO re-apply of the Pod itself."
else
  echo "FAIL: /etc/config/MESSAGE never became v2 within 120s (still '$file_val')."
  FAIL=1
fi

echo "==> re-checking env var MESSAGE_ENV — this MUST still say v1"
env_val=$(kubectl exec config-test -n "$NS" -- printenv MESSAGE_ENV 2>/dev/null)
if [ "$env_val" = "v1" ]; then
  echo "    OK — MESSAGE_ENV is still v1, exactly as expected: env vars are captured once at container start and never revisited."
else
  echo "FAIL: MESSAGE_ENV changed to '$env_val' without a restart — that would be surprising/wrong Kubernetes behavior."
  FAIL=1
fi

restarts=$(kubectl get pod config-test -n "$NS" -o jsonpath='{.status.containerStatuses[0].restartCount}')
echo "==> restartCount=$restarts (should be 0 throughout this whole lab)"
if [ "$restarts" != "0" ]; then
  echo "FAIL: restartCount is $restarts, expected 0"
  FAIL=1
fi

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS — file auto-updated, env var stayed frozen, zero restarts. That asymmetry is the whole lesson."
  exit 0
else
  echo
  echo "RESULT: FAIL — see messages above."
  exit 1
fi
