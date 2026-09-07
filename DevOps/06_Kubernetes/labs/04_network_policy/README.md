# Lab 4 — NetworkPolicy: default-deny + selective allow

**Goal:** Kubernetes networking is **flat by default** — any Pod can reach
any other Pod's IP across the entire cluster, across namespaces, with zero
restriction, unless a NetworkPolicy says otherwise. This is exactly the
question the existing `../../practical/01_kubernetes_lab.md` self-check
checklist asks ("Can you write a NetworkPolicy or explain why K8s networking
is flat-by-default?") but never actually builds — this lab builds it, live.

> **Why this needs Calico, not kindnet:** kind's default CNI (kindnet) accepts
> NetworkPolicy objects without complaint and enforces *none* of them. If
> `../_setup/setup.sh` didn't install Calico, every check below would show
> "allowed" even with a deny-all policy applied — not because your YAML is
> wrong, but because nothing on the cluster reads it. In a real cluster,
> checking whether the CNI enforces NetworkPolicy at all is the first thing
> to verify when a policy "isn't working."

**Task:** Open `manifest.yaml`. The `web-netpol` NetworkPolicy currently has
`ingress: []` — combined with `policyTypes: [Ingress]`, that means **deny all
ingress, no exceptions at all**, even from Pods that should be allowed. Add
an ingress rule allowing traffic only from Pods labeled `role: allowed`:
```yaml
  ingress:
    - from:
        - podSelector:
            matchLabels:
              role: allowed
```

**Verify:**
```bash
./verify.sh
```
Spins up two throwaway client Pods: one labeled `role=allowed`, one with no
role label at all. Confirms the labeled one gets `HTTP 200` from the `web`
Service and the unlabeled one times out (`HTTP 000`). If you left
`ingress: []` as-is, BOTH clients get blocked — the script tells you that
specifically, rather than a generic failure.

**SOCH:**
- The blocked client isn't in any special "denied" list — it's just a Pod
  with no label matching the policy's `from:` selector. What does that tell
  you about how NetworkPolicy actually decides allow/deny — is it a blocklist
  or an allowlist model, and why does that matter when you add a THIRD kind
  of client later?
- This policy only restricts **Ingress** to `app=web`. If `web`'s container
  itself needed to call out to an external API, would this policy block that?
  What would you need to add, and to which `policyTypes` entry?
