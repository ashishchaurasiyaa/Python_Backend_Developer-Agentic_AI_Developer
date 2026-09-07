# Lab 3 — OOMKill vs CPU throttling: same `limits:` block, opposite outcomes

**Goal:** Prove, live, that going over a **memory** limit and going over a
**CPU** limit are not "the same kind of problem at different severities" —
they're two entirely different mechanisms with opposite consequences. Memory:
the kernel OOM killer sends SIGKILL, the container dies (exit 137, reason
`OOMKilled`), no graceful shutdown possible. CPU: the kernel's CFS scheduler
just gives the process fewer timeslices — the process keeps running, slower,
forever, never killed for it.

**Task:** Open `manifest.yaml`. `mem-hog` runs `stress --vm-bytes 150M`
against a memory limit of `500Mi` right now — comfortably under, so nothing
happens. Lower `resources.limits.memory` to something below `150M` (try
`100Mi`) so the allocation actually exceeds the limit and the OOM killer
fires. `cpu-hog` needs no changes — it's the fixed contrast case.

**Verify:**
```bash
./verify.sh
```
Polls `mem-hog` for up to 60s for a terminal state and asserts
`reason=OOMKilled`, `exitCode=137`. Separately watches `cpu-hog` for 15s and
asserts it stays `Running` with `restartCount=0` the entire time. Where the
node's cgroup v2 stats are readable, it also prints `nr_throttled` from
`cpu.stat` as bonus live evidence that the kernel actually throttled it.

**SOCH:**
- `kubectl describe pod` on an OOMKilled pod and on a normally-crashed pod
  (from `../../practical/01_kubernetes_lab.md` Lab 4's "bad command" case)
  both eventually show `CrashLoopBackOff` if `restartPolicy` allows retries.
  Given both end up looking similar in `kubectl get pods` STATUS, what's the
  one field you'd check FIRST to tell "my app crashed itself" apart from "the
  memory limit killed it"?
- `cpu-hog`'s process never dies, never restarts, and (per the bonus cgroup
  evidence) is verifiably being throttled — yet `kubectl get pods` shows
  nothing unusual at all, no event, no warning. What does that imply about
  how you'd actually *notice* a CPU-limit-starved service in production if
  you were only watching pod status and not resource metrics?
