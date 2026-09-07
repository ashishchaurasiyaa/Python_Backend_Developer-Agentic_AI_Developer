# Kubernetes Labs — Runnable Exercises

`../practical/01_kubernetes_lab.md` already has 4 excellent walkthroughs
(Deployments/rolling updates, ConfigMaps/Secrets/StatefulSets,
Ingress/HPA/RBAC, CrashLoopBackOff diagnosis) — but every one of them ships
its solution inline in the same file, so there's nothing left to actually
solve. This folder is for *doing*: TODO-stub manifests you fill in yourself,
each with a `verify.sh` that checks real cluster state and tells you PASS or
FAIL — not "looks right", a script that actually breaks the thing and checks
whether your fix works. Five labs, each covering something the walkthrough
doc doesn't: readiness-driven Service routing, ConfigMap update propagation,
resource-limit failure modes, NetworkPolicy enforcement, and Job retry
semantics.

## Setup (once)

You need a local cluster with a CNI that actually **enforces**
NetworkPolicy — kind's default CNI (kindnet) silently ignores NetworkPolicy
objects, which would make Lab 4 always look like it passes even when it
doesn't. `_setup/setup.sh` creates a kind cluster with Calico instead:

```bash
cd DevOps/06_Kubernetes/labs
brew install kind kubernetes-cli          # if you don't have them
_setup/setup.sh                           # creates the cluster + Calico, ~2 min
```

Each lab is fully self-contained — its `verify.sh` applies its own
manifest, checks it, and cleans up after itself (via a trap), so labs can be
run in any order without leftover state.

Teardown when you're done with all of them:
```bash
_setup/teardown.sh
```

## Labs

| # | Lab | What it proves | New concept vs. `../practical/` |
|---|---|---|---|
| 1 | [01_readiness_gating](01_readiness_gating) | A failed readiness probe pulls a Pod out of the Service's endpoints — Pod keeps running, zero restarts | The walkthrough doc covers *liveness* -> restart; this is *readiness* -> traffic routing, a different mechanism entirely |
| 2 | [02_configmap_reload](02_configmap_reload) | A ConfigMap mounted as a **file** updates on its own (~1 min); the same value as an **env var** never updates without a restart | The walkthrough doc covers Secret-as-file vs ConfigMap-as-env *delivery*; this covers what happens on *update*, live |
| 3 | [03_oomkill_vs_throttling](03_oomkill_vs_throttling) | A memory-limit breach gets a container SIGKILLed (`OOMKilled`, exit 137); a CPU-limit breach just throttles it — never killed | A 4th, distinct failure mode next to the walkthrough doc's 3 CrashLoopBackOff causes |
| 4 | [04_network_policy](04_network_policy) | Kubernetes networking is flat by default; a NetworkPolicy can default-deny and selectively allow by Pod label | Explicitly the one item the walkthrough doc's own self-check checklist asks about but never builds |
| 5 | [05_jobs_cronjobs](05_jobs_cronjobs) | `restartPolicy: OnFailure` retries the same Pod (surviving volumes included); an unset `backoffLimit` takes minutes to give up, not seconds | Jobs/CronJobs are a "Quick Concept" in `01_architecture_objects.md` but never hands-on exercised anywhere in this phase |

## Protocol

```
1. Open the lab's manifest.yaml, read the comment block at the top
2. Fill in the TODO(s)
3. Run ./verify.sh -> PASS moves you to the next lab; FAIL tells you
   specifically what it expected vs what it saw
4. Answer the README's SOCH questions out loud before moving on -- that's
   what actually gets asked in an interview, not the YAML syntax
```

## Checklist

- [ ] Lab 1 — Readiness gating & Service endpoint exclusion
- [ ] Lab 2 — ConfigMap volume hot-reload vs env-var staleness
- [ ] Lab 3 — OOMKill vs CPU throttling
- [ ] Lab 4 — NetworkPolicy default-deny + selective allow
- [ ] Lab 5 — Job completion guarantees & backoffLimit
