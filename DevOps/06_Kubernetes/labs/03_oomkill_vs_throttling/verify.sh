#!/usr/bin/env bash
# Self-checking verifier for Lab 3 — OOMKill vs CPU throttling.
# PASS only if mem-hog is actually killed with reason OOMKilled/exit 137,
# AND cpu-hog stays Running with zero restarts the whole time.
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

echo "==> polling up to 60s for mem-hog to reach a terminal state"
reason=""
for i in $(seq 1 30); do
  reason=$(kubectl get pod mem-hog -n "$NS" -o jsonpath='{.status.containerStatuses[0].state.terminated.reason}' 2>/dev/null)
  if [ -n "$reason" ]; then break; fi
  sleep 2
done

if [ "$reason" = "OOMKilled" ]; then
  exit_code=$(kubectl get pod mem-hog -n "$NS" -o jsonpath='{.status.containerStatuses[0].state.terminated.exitCode}')
  echo "    OK — mem-hog terminated with reason=OOMKilled, exitCode=$exit_code (expected 137) after ~$((i*2))s"
  if [ "$exit_code" != "137" ]; then
    echo "FAIL: exitCode was $exit_code, expected 137 (SIGKILL from the OOM killer)"
    FAIL=1
  fi
elif [ -z "$reason" ]; then
  echo "FAIL: mem-hog never reached a terminal state within 60s — it's still running."
  echo "      Most likely cause: resources.limits.memory in manifest.yaml is still too high"
  echo "      (the TODO wasn't done) so stress's 150M allocation fit comfortably under it."
  FAIL=1
else
  echo "FAIL: mem-hog terminated with reason='$reason', expected 'OOMKilled'"
  FAIL=1
fi

echo "==> checking cpu-hog stays Running (throttled, never killed) for 15s"
cpu_ok=1
for i in $(seq 1 5); do
  phase=$(kubectl get pod cpu-hog -n "$NS" -o jsonpath='{.status.phase}' 2>/dev/null)
  restarts=$(kubectl get pod cpu-hog -n "$NS" -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null)
  if [ "$phase" != "Running" ] || [ "${restarts:-0}" != "0" ]; then
    cpu_ok=0
    echo "FAIL: cpu-hog phase=$phase restarts=$restarts at t=$((i*3))s — it should stay Running with 0 restarts, CPU limits don't kill anything"
    FAIL=1
    break
  fi
  sleep 3
done
[ "$cpu_ok" = "1" ] && echo "    OK — cpu-hog stayed Running, 0 restarts, the whole time (throttled, not killed)"

# Best-effort extra evidence: cgroup v2 exposes nr_throttled directly.
throttled=$(kubectl exec cpu-hog -n "$NS" -- sh -c 'cat /sys/fs/cgroup/cpu.stat 2>/dev/null | grep nr_throttled' 2>/dev/null)
if [ -n "$throttled" ]; then
  echo "    bonus evidence — cgroup cpu.stat on cpu-hog: $throttled (nr_throttled > 0 means the kernel actually throttled it)"
fi

if [ "$FAIL" = "0" ]; then
  echo
  echo "PASS — mem-hog OOMKilled (exit 137), cpu-hog throttled-but-alive. Same 'limits:' block, opposite failure modes."
  exit 0
else
  echo
  echo "RESULT: FAIL — see messages above."
  exit 1
fi
