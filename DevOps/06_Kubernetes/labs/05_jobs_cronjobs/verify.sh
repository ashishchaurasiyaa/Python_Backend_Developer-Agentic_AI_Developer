#!/usr/bin/env bash
# Self-checking verifier for Lab 5 — Job completion guarantees & backoffLimit.
# PASS only if job-succeeds eventually reports succeeded=1, AND job-fails
# reaches the Failed condition within a bounded time (proving backoffLimit
# was actually set low, not left at the slow default).
set -uo pipefail
cd "$(dirname "$0")"
NS=k8s-labs
FAIL=0

cleanup() {
  kubectl delete -f manifest.yaml -n "$NS" --ignore-not-found >/dev/null 2>&1
}
trap cleanup EXIT

echo "==> applying manifest.yaml"
kubectl apply -f manifest.yaml -n "$NS" >/dev/null

echo "==> polling up to 75s for job-succeeds to report succeeded=1 (needs 3 attempts with growing backoff)"
ok=0
for i in $(seq 1 25); do
  succeeded=$(kubectl get job job-succeeds -n "$NS" -o jsonpath='{.status.succeeded}' 2>/dev/null)
  if [ "$succeeded" = "1" ]; then ok=1; break; fi
  sleep 3
done
if [ "$ok" = "1" ]; then
  echo "    OK — job-succeeds reported succeeded=1 after ~$((i*3))s (took 3 attempts on the SAME pod, same emptyDir)"
else
  echo "FAIL: job-succeeds never reported succeeded=1 within 75s — check 'kubectl describe job/job-succeeds -n $NS'"
  FAIL=1
fi

echo "==> polling up to 40s for job-fails to reach condition Failed=True"
failed_ok=0
for i in $(seq 1 20); do
  cond=$(kubectl get job job-fails -n "$NS" -o jsonpath="{.status.conditions[?(@.type=='Failed')].status}" 2>/dev/null)
  if [ "$cond" = "True" ]; then failed_ok=1; break; fi
  sleep 2
done

if [ "$failed_ok" = "1" ]; then
  failed_count=$(kubectl get job job-fails -n "$NS" -o jsonpath='{.status.failed}')
  echo "    OK — job-fails reached Failed=True after ~$((i*2))s, with $failed_count failed pod attempt(s)."
  if [ "$failed_count" != "2" ]; then
    echo "    NOTE: expected 2 failed attempts for backoffLimit=1 (initial + 1 retry), saw $failed_count -- check the exact value you set."
  fi
else
  echo "FAIL: job-fails never reached Failed=True within 40s."
  echo "      Most likely cause: backoffLimit wasn't added (TODO not done) -- the default (6)"
  echo "      with Kubernetes' growing retry backoff takes several MINUTES to give up, not 40s."
  FAIL=1
fi

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS — job-succeeds completed via same-pod retries, job-fails gave up FAST because backoffLimit was set low."
  exit 0
else
  echo
  echo "RESULT: FAIL — see messages above."
  exit 1
fi
