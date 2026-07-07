# 20 — Blue-Green Deployment

> Run two identical production environments, only one live at a time. Switch traffic instantly, keep the old one as an instant rollback.

---

## Why It Matters

Rolling deployments (updating pods one-by-one) risk a window where old and
new versions run simultaneously, which is fine for stateless changes but
dangerous for breaking API/schema changes. Blue-green sidesteps this by never
mixing versions in production traffic — it's either all-old or all-new.

Senior interview: "How do you deploy with zero downtime AND an instant
rollback if something's wrong?" → blue-green, not just rolling update.

---

## Core Concept

```
                    ┌─────────────┐
   Load Balancer /  │   BLUE       │  ← currently LIVE (v1.2)
   Router           │  (v1.2)      │
        │           └─────────────┘
        │
        │           ┌─────────────┐
        └─────────► │   GREEN      │  ← idle, being deployed (v1.3)
     (switch here)   │  (v1.3)      │
                     └─────────────┘

Deploy v1.3 to GREEN (idle) → run smoke tests against GREEN directly →
flip the router to point at GREEN → BLUE becomes idle (old version, kept warm)
```

**Rollback:** if v1.3 misbehaves after the switch, flip the router back to
BLUE — instant, no redeploy needed, since BLUE never stopped running.

---

## Kubernetes implementation (Service selector swap)

```yaml
# Two Deployments, same app, different version labels
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-blue
spec:
  replicas: 3
  selector:
    matchLabels: { app: myapp, version: blue }
  template:
    metadata:
      labels: { app: myapp, version: blue }
    spec:
      containers:
        - name: myapp
          image: myapp:v1.2
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp-green
spec:
  replicas: 3
  selector:
    matchLabels: { app: myapp, version: green }
  template:
    metadata:
      labels: { app: myapp, version: green }
    spec:
      containers:
        - name: myapp
          image: myapp:v1.3
---
# The Service currently routes to "blue" — this ONE line is the switch
apiVersion: v1
kind: Service
metadata:
  name: myapp
spec:
  selector:
    app: myapp
    version: blue      # ← change to "green" to cut over, instantly
  ports:
    - port: 80
```

```bash
# The actual cutover — one command, near-instant
kubectl patch service myapp -p '{"spec":{"selector":{"version":"green"}}}'

# Rollback is the same command, reversed
kubectl patch service myapp -p '{"spec":{"selector":{"version":"blue"}}}'
```

---

## Blue-Green vs Rolling vs Canary (the actual interview comparison)

| Strategy | Traffic mixing during deploy | Rollback speed | Infra cost |
|---|---|---|---|
| **Rolling update** | Yes — old + new pods serve traffic simultaneously | Slower (roll back pod-by-pod) | Low (no duplicate fleet) |
| **Blue-Green** | No — instant full cutover, no mixed-version window | Instant (flip back) | High (2x fleet running simultaneously, even briefly) |
| **Canary** | Yes, deliberately — small % of traffic to new version first | Fast (just remove canary) | Low-medium |

**When to pick blue-green specifically:** breaking database schema changes,
breaking API contract changes, or anything where even a brief mixed-version
window would cause errors — rolling updates can't guarantee that isolation,
blue-green can.

**The real cost tradeoff to say out loud:** blue-green needs 2x the
production capacity running at once (even if briefly), which rolling updates
avoid — this is why many teams default to rolling/canary and reserve
blue-green for genuinely risky releases.

---

## The database problem (the part interviewers actually probe)

```
Blue-green is easy for STATELESS app servers. It's hard the moment
BLUE and GREEN share the same database, and the new version needs a
schema change.

If GREEN's code expects a new column that doesn't exist yet when BLUE
is still live and also querying that table → BLUE breaks.
```

**Fix pattern — expand/contract migrations** (already covered in
[26_expand_contract_migrations.md](../../00_Year0-2_Junior/04_Database_SQL/26_expand_contract_migrations.md)):
add new columns/tables in a backward-compatible way *before* the blue-green
switch, so both BLUE (old code) and GREEN (new code) can run against the
same schema simultaneously during the cutover window.

---

## Interview Q&A

**Q: Blue-green vs canary — which gives you real-user validation before full cutover?**
A: Canary — it deliberately routes a small percentage of real traffic to the
new version first, observing error rates before widening. Blue-green is all-or-nothing
at cutover; you validate via smoke tests against the idle environment, not real user traffic.

**Q: What's the biggest practical blocker to blue-green in a real system?**
A: Shared stateful resources — mainly the database. Two app versions can't
safely run against an incompatible schema. Requires backward-compatible
"expand/contract" migrations so both old and new code tolerate the same schema.

**Q: Why does blue-green cost more than rolling updates?**
A: You run two full production-sized environments simultaneously (even if
GREEN is only "live" for testing before cutover) — double the compute during
that window, versus rolling updates which only ever run slightly more than
your normal fleet size (a few extra pods during the rollout).

---

Related: [11_deployment_decision_framework.md](11_deployment_decision_framework.md)
(when to pick this vs canary vs rolling), `13_gitops_argocd_flux.md` (Argo
Rollouts supports blue-green natively as a CRD, not just manual selector swaps).
