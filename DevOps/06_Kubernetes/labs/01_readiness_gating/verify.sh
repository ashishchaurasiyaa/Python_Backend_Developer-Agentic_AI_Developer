#!/usr/bin/env bash
# Self-checking verifier for Lab 1 — readiness gating.
# PASS only if a Pod whose /healthz.html was deleted actually gets pulled out
# of the Service's endpoint list, and comes back once healthz.html returns.
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

echo "==> waiting up to 60s for the Deployment to report available"
if ! kubectl wait --for=condition=Available deployment/web -n "$NS" --timeout=60s >/dev/null 2>&1; then
  echo "FAIL: Deployment never became Available — check 'kubectl describe deployment/web -n $NS'"
  exit 1
fi

echo "==> confirming 3 endpoints registered"
n=$(kubectl get endpoints web -n "$NS" -o jsonpath='{.subsets[0].addresses}' 2>/dev/null | grep -o '"ip"' | wc -l | tr -d ' ')
if [ "$n" != "3" ]; then
  echo "FAIL: expected 3 endpoint addresses before breaking anything, got $n"
  exit 1
fi
echo "    OK — 3/3 endpoints"

pod=$(kubectl get pods -n "$NS" -l app=web -o jsonpath='{.items[0].metadata.name}')
echo "==> breaking readiness on $pod (deleting /www/healthz.html, NOT killing the process)"
kubectl exec "$pod" -n "$NS" -- rm -f /www/healthz.html

echo "==> polling up to 15s for the Service to drop it to 2 endpoints"
ok=0
for i in $(seq 1 15); do
  n=$(kubectl get endpoints web -n "$NS" -o jsonpath='{.subsets[0].addresses}' 2>/dev/null | grep -o '"ip"' | wc -l | tr -d ' ')
  if [ "$n" = "2" ]; then ok=1; break; fi
  sleep 1
done

if [ "$ok" = "1" ]; then
  echo "    OK — endpoints dropped to 2/3 after ${i}s. readinessProbe is wired correctly."
  ready=$(kubectl get pod "$pod" -n "$NS" -o jsonpath='{.status.containerStatuses[0].ready}')
  restarts=$(kubectl get pod "$pod" -n "$NS" -o jsonpath='{.status.containerStatuses[0].restartCount}')
  echo "    pod.ready=$ready restartCount=$restarts (should be ready=false, restarts=0 — it was never killed)"
  if [ "$restarts" != "0" ]; then
    echo "FAIL: restartCount is $restarts, expected 0 — something restarted the container, that's a LIVENESS behavior, not readiness"
    FAIL=1
  fi
else
  echo "FAIL: endpoints never dropped below 3 after 15s."
  echo "      Most likely cause: no readinessProbe was added to manifest.yaml (TODO not done),"
  echo "      so Kubernetes still thinks the Pod is Ready even with healthz.html gone."
  FAIL=1
fi

echo "==> restoring healthz.html"
kubectl exec "$pod" -n "$NS" -- sh -c "echo ok > /www/healthz.html"

echo "==> polling up to 15s for the Service to return to 3 endpoints"
ok2=0
for i in $(seq 1 15); do
  n=$(kubectl get endpoints web -n "$NS" -o jsonpath='{.subsets[0].addresses}' 2>/dev/null | grep -o '"ip"' | wc -l | tr -d ' ')
  if [ "$n" = "3" ]; then ok2=1; break; fi
  sleep 1
done

if [ "$ok2" = "1" ]; then
  echo "    OK — back to 3/3 endpoints after ${i}s, no manual restart needed."
else
  if [ "$FAIL" = "0" ]; then
    echo "FAIL: healthz.html was restored but the Pod never rejoined the Service."
    FAIL=1
  fi
fi

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS — readiness gating verified: bad health -> removed from Service, good health -> rejoined, zero restarts throughout."
  exit 0
else
  echo
  echo "RESULT: FAIL — see messages above."
  exit 1
fi
