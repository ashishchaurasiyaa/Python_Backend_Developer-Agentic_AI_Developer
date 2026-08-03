# DevOps Best Practices — Hands-On Lab
**DevOps Track · Phase 20 Practical**

## Prerequisites

Mix of local tooling and written exercises — most labs here are process/design artifacts (runbooks, rollout plans) since that's what this phase is actually about in practice, plus one hands-on Kubernetes rolling-update lab if you have a local cluster available.

- Docker + Docker Compose for the containerized pieces
- **Optional but recommended for Lab 2**: a local Kubernetes cluster — `minikube`, `kind`, or Docker Desktop's built-in Kubernetes. If you don't have one, the lab includes a manifest-only fallback where you reason through the rollout mechanics from the YAML and `kubectl` command output alone (still valuable, less hands-on)
- `kubectl` CLI if using a local cluster
- A text editor for writing the runbook/rollout-plan documents in Labs 3-4 — these are meant to be written artifacts, treat them like real on-call documentation, not throwaway notes
- No AWS account needed — the cost-optimization concepts in Lab 4 use S3 lifecycle JSON as a design artifact, not a live bucket

---

## Lab 1: Basic — Write and Validate a Zero-Downtime Deployment Checklist Against a Real App

**Objective:** Take the lesson's Zero-Downtime Deployment Checklist and apply it item-by-item to a real (small) service, finding the gaps.

**Task:**
1. Write a minimal Flask app with a `/healthz` endpoint that currently just returns `200 OK` unconditionally (this is the "lying health check" the lesson warns about) and a `/work` endpoint that sleeps 3 seconds before responding (simulating a slow in-flight request).
2. Containerize it with a `Dockerfile`, and write a Kubernetes `Deployment` manifest with `replicas: 3`, a `livenessProbe`, and a `readinessProbe` both pointed at `/healthz`.
3. Go through the lesson's checklist item by item against your current manifest/app and mark each as PASS or FAIL:
   - Health checks accurate (does `/healthz` actually check anything, or just return 200)?
   - Readiness gates traffic before join?
   - Connection draining / graceful shutdown on SIGTERM?
   - `terminationGracePeriodSeconds` set appropriately for your slowest endpoint?
   - Backward-compatible DB migrations (N/A here, no DB — note why)?
   - Rollback plan tested?
   - Session state external?
4. Fix at least 3 of the FAILs: make `/healthz` check something real (even a fake dependency flag), add a SIGTERM handler that stops accepting new connections and waits for in-flight ones, and set `terminationGracePeriodSeconds` to comfortably exceed your slowest endpoint's duration.
5. Re-run the checklist and confirm those items now PASS.

<details>
<summary>Solution / walkthrough</summary>

```python
# app.py — BEFORE (deliberately has the lying health check bug)
from flask import Flask
import time

app = Flask(__name__)

@app.route("/healthz")
def healthz():
    return "OK", 200   # FAIL: doesn't check anything real

@app.route("/work")
def work():
    time.sleep(3)
    return {"status": "done"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

```yaml
# deployment.yaml — BEFORE
apiVersion: apps/v1
kind: Deployment
metadata:
  name: work-service
spec:
  replicas: 3
  selector:
    matchLabels: { app: work-service }
  template:
    metadata:
      labels: { app: work-service }
    spec:
      containers:
        - name: work-service
          image: work-service:v1
          ports: [{ containerPort: 8000 }]
          livenessProbe:
            httpGet: { path: /healthz, port: 8000 }
          readinessProbe:
            httpGet: { path: /healthz, port: 8000 }
          # no terminationGracePeriodSeconds override — defaults to 30s
```

**Checklist pass:**
| Item | Status | Why |
|---|---|---|
| Health checks accurate | FAIL | `/healthz` returns 200 unconditionally, checks nothing |
| Readiness gates traffic | PASS | readinessProbe is wired, K8s does gate on it |
| Connection draining / graceful shutdown | FAIL | no SIGTERM handler, Flask dev server just dies |
| terminationGracePeriodSeconds | FAIL | default 30s, untested against the 3s `/work` endpoint (looks OK on paper but never verified) |
| Backward-compatible migrations | N/A | no DB in this service |
| Rollback plan tested | FAIL | never run `kubectl rollout undo` against this manifest |
| Session state external | PASS | stateless, no in-memory session data |

```python
# app.py — AFTER, fixes applied
from flask import Flask
import time, signal, sys, threading

app = Flask(__name__)
shutting_down = threading.Event()

@app.route("/healthz")
def healthz():
    # check something real — even a simple in-process dependency flag counts
    if shutting_down.is_set():
        return "SHUTTING DOWN", 503   # stop passing readiness once draining starts
    return "OK", 200

@app.route("/work")
def work():
    time.sleep(3)
    return {"status": "done"}

def handle_sigterm(signum, frame):
    print("SIGTERM received — failing readiness, draining in-flight requests")
    shutting_down.set()
    time.sleep(5)   # grace window for in-flight /work calls (3s) to finish
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_sigterm)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

```yaml
# deployment.yaml — AFTER
spec:
  template:
    spec:
      terminationGracePeriodSeconds: 15   # comfortably exceeds work's 3s + drain buffer
      containers:
        - name: work-service
          readinessProbe:
            httpGet: { path: /healthz, port: 8000 }
            periodSeconds: 3   # check often enough to notice the 503 quickly
```

```bash
# validate the rollback plan item — actually run it, don't just assume it works
kubectl apply -f deployment.yaml
kubectl set image deployment/work-service work-service=work-service:v2
kubectl rollout status deployment/work-service
kubectl rollout undo deployment/work-service
kubectl rollout status deployment/work-service
# confirms v1 is back — THIS is what "tested" means, not "should work"
```

Re-run the checklist: health checks now check real state, graceful shutdown fails readiness before draining, `terminationGracePeriodSeconds` is deliberately sized, and rollback has actually been executed once, not assumed.
</details>

---

## Lab 2: Intermediate — Watch a Rolling Update's `maxSurge`/`maxUnavailable` Mechanics Live

**Objective:** Reproduce the exact `replicas: 10, maxSurge: 2, maxUnavailable: 1` walkthrough from the lesson and WATCH pod counts change in real time, instead of just reading the diagram.

**Task:**
1. Using a local cluster (minikube/kind/Docker Desktop K8s), deploy the Lab 1 app with `replicas: 10`, `maxSurge: 2`, `maxUnavailable: 1`, and a readiness probe with a deliberate `initialDelaySeconds: 5` so the rollout is slow enough to observe.
2. In one terminal, run `kubectl get pods -w` (watch mode) to observe pod churn live.
3. In another terminal, trigger a rollout: `kubectl set image deployment/work-service work-service=work-service:v2`.
4. Record the pod count over time — you should briefly see MORE than 10 pods (surge) and NEVER fewer than 9 (10 - maxUnavailable).
5. Now deliberately break the new version — set the readiness probe path to something that 404s in v2's image, and trigger another rollout. Confirm Kubernetes gets STUCK (new pods never become ready, old pods are never fully replaced) rather than completing a broken rollout — this proves the readiness probe is what gates progression, per the lesson.
6. Recover: `kubectl rollout undo deployment/work-service` and confirm it returns to the last good state.

<details>
<summary>Solution / walkthrough</summary>

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: work-service
spec:
  replicas: 10
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 2
      maxUnavailable: 1
  selector:
    matchLabels: { app: work-service }
  template:
    metadata:
      labels: { app: work-service }
    spec:
      terminationGracePeriodSeconds: 15
      containers:
        - name: work-service
          image: work-service:v1
          ports: [{ containerPort: 8000 }]
          readinessProbe:
            httpGet: { path: /healthz, port: 8000 }
            initialDelaySeconds: 5
            periodSeconds: 3
```

```bash
kubectl apply -f deployment.yaml
kubectl rollout status deployment/work-service   # wait for initial 10/10 ready
```

```bash
# terminal 1
kubectl get pods -w
```

```bash
# terminal 2
docker build -t work-service:v2 .   # same app, tagged v2 (or a trivial change)
kubectl set image deployment/work-service work-service=work-service:v2
```

Expected pattern in terminal 1 (matching the lesson's walkthrough exactly):
```
Start:   10 pods Running (v1)
+2 new pods appear, Pending -> ContainerCreating -> Running -> (5s delay) -> Ready
  -> total visible: up to 12 (surge)
Once 2 new pods pass readiness: 1 old v1 pod Terminating
  -> total drops back toward 11, then 10 as terminating pod exits
... repeats until 10 pods are all v2, 0 are v1
```

```bash
kubectl get replicaset -l app=work-service
# watch OLD replicaset's desired count march down to 0 while NEW marches up to 10
```

**Step 5 — broken rollout:**

```yaml
# readinessProbe now points at a path that doesn't exist in v2
readinessProbe:
  httpGet: { path: /this-path-404s, port: 8000 }
```

```bash
kubectl set image deployment/work-service work-service=work-service:v3
kubectl rollout status deployment/work-service
# hangs — "Waiting for deployment "work-service" rollout to finish: 2 out of
# 10 new replicas have been updated..." and never progresses past maxSurge's
# worth of new (permanently unready) pods

kubectl get pods
# new v3 pods stuck in Running but 0/1 READY — never terminates more old pods
# because K8s won't drop below (10 - maxUnavailable) READY capacity, and the
# new pods never count as ready
```

```bash
kubectl rollout undo deployment/work-service
kubectl rollout status deployment/work-service
# returns to 10/10 v2 pods, all healthy
```

Why this matters: this is the single most concrete proof of the lesson's claim that "a broken or missing readiness probe is the #1 cause of a rolling update taking down capacity" — except here it's the OPPOSITE demonstration: the readiness probe correctly PREVENTS a broken rollout from ever completing, protecting capacity at the cost of a stuck deployment that needs a human to notice and roll back. Both directions (a probe that lies and passes broken pods vs. a probe that correctly blocks them) are worth having felt once.
</details>

---

## Lab 3: Production-Style — Write a Canary Rollout Plan + Rollback Runbook for a Real Service

**Objective:** Produce the actual written artifact a senior engineer would attach to a risky production change — directly implementing the lesson's framing: "I shifted 5% of canary traffic, watched error rate for 3 minutes, caught the regression before it hit 100%... that sentence is what gets you hired at senior level."

**Task:** Pick a real (or realistic invented) service change — e.g., "orders-api is switching its payment provider integration from Provider A to Provider B." Write a complete rollout plan + runbook document (400-600 words) with these sections, matching the structures from the lesson:

1. **Change summary** — what's changing, why, and the blast radius if it goes wrong.
2. **Canary stages** — the specific traffic percentages and dwell time at each stage (mirror the lesson's `5% → 25% → 50% → 100%` pattern), and the EXACT metrics gate for progressing (error rate threshold, latency threshold, a business metric).
3. **Automated vs manual gates** — which stage transitions could be automated (Flagger/Argo Rollouts style, per the lesson) vs which need a human sign-off, and why.
4. **Rollback trigger conditions** — the specific numbers that trigger an automatic or manual rollback, not vague language like "if things look bad."
5. **Rollback runbook** — using the lesson's Runbook Structure (Detection → Immediate check → Likely causes → Mitigation → Escalation path → Postmortem), write the actual runbook for THIS change.
6. **Feature flag interplay** — per the lesson's point that flags and canary/rolling deploys are complementary — does this change also get a feature flag, and if so what does the flag control that the canary percentage doesn't?

<details>
<summary>Solution / walkthrough</summary>

**Example artifact — "Payment Provider Migration: Provider A → Provider B"**

**1. Change summary**
`orders-api`'s `charge_payment()` call switches from Provider A's SDK to Provider B's. Blast radius if broken: failed/duplicate charges on the checkout path — a SEV1-class failure mode (real money, real customers) if it goes fully wrong, which is exactly why this ships via canary rather than a rolling update or blue-green all-at-once cutover.

**2. Canary stages**
```
Stage 1:  5% traffic  -> dwell 15 min  (payment-specific: longer than the
                                          lesson's generic 10 min, since
                                          payment failures may surface on
                                          retry/webhook delay, not instantly)
Stage 2: 25% traffic  -> dwell 15 min
Stage 3: 50% traffic  -> dwell 20 min
Stage 4: 100% traffic -> monitor 30 min post-cutover before declaring done

Metrics gate at EACH stage (must ALL pass to progress):
  - payment_error_rate < 0.5%  (tighter than the lesson's generic 1% —
    justified because payment errors are costlier than a generic 5xx)
  - p99 checkout latency < 2x baseline
  - business metric: checkout_success_rate not down more than 1 percentage
    point vs the 7-day trailing average for this time-of-day
```

**3. Automated vs manual gates**
Stage 1→2 and 2→3 transitions are automated (Argo Rollouts querying Prometheus for the metrics gate above) — these are narrow, well-understood thresholds where a human isn't adding judgment, just latency. Stage 3→4 (50%→100%) requires a MANUAL sign-off from the on-call payments engineer — going to 100% removes the safety net entirely (no more "some users still on the old path" fallback), so a human explicitly confirms the dwell-period metrics AND checks the payment provider's own status page before that step, which automation can't reliably do.

**4. Rollback trigger conditions**
```
AUTOMATIC rollback (no human needed to trigger) if, at any stage:
  - payment_error_rate > 2%  for any 2 consecutive 1-minute windows
  - 5 or more duplicate-charge reports from the reconciliation job in 10 min

MANUAL rollback (on-call decides) if:
  - Provider B's status page shows a degraded/partial outage
  - Support ticket volume for "payment failed" spikes qualitatively,
    even if automated metrics haven't crossed the hard threshold yet
```

**5. Rollback runbook**
```
1. Detection: PagerDuty alert "payment_error_rate > 2%" fires from the
   Prometheus rule watching the canary's own metrics, OR manual trigger
   above.
2. Immediate check: open the "Payment Provider Migration" Grafana dashboard
   (linked in the alert) — confirm this is Provider B specifically, not a
   pre-existing unrelated issue (e.g., check Provider A's error rate is
   still flat/normal on the 95% control group).
3. Likely causes (ranked from past incidents of this type):
   a. Provider B API credentials/config mismatch in prod (60% of past
      provider-migration incidents) — check the last config diff first
   b. Provider B rate-limiting our traffic once volume crossed a stage
      threshold (25%) — check Provider B's response codes for 429s
   c. Timeout mismatch — Provider B's p99 latency is genuinely higher
      than Provider A's and our client timeout is too aggressive
4. Mitigation: `kubectl argo rollouts abort orders-api` (reverts traffic
   weight to 0% canary / 100% stable instantly) OR flip the
   `payment-provider-b` feature flag to `false` (see section 6) if the
   flag is the finer-grained control — prefer the flag flip, it's faster
   than a rollout abort.
5. Escalation path: on-call payments engineer (primary) -> payments team
   lead (if unresolved in 15 min) -> Provider B's support escalation
   contact (if their API is confirmed the cause).
6. Postmortem: mandatory within 48h per the lesson's SEV1/SEV2 rule,
   given real-money impact — timeline, root cause (5-whys), action items
   with owners and due dates, filed as a tracked ticket not just a doc.
```

**6. Feature flag interplay**
Yes — `payment-provider-b` flag wraps the provider selection logic itself, checked INSIDE the code path regardless of which canary percentage routed the request there. This gives a rollback mechanism faster than even an Argo Rollouts abort (a flag flip propagates in seconds via the cached-flag-check pattern from the lesson, vs. a rollout abort which still needs the mesh/LB to re-converge traffic weights). The canary percentage controls CODE risk (is the new code path stable under real traffic); the flag controls FEATURE risk (can we instantly kill the new provider entirely, even mid-request-handling, without touching deployment infrastructure) — exactly the complementary-not-substitute relationship the lesson describes.
</details>

---

## Lab 4 (optional): Disaster Recovery Drill — Restore from Backup and Prove RTO/RPO

**Objective:** The lesson's own non-negotiable practice: "untested backups are a hypothesis, not a backup." Actually run a restore drill and MEASURE whether you meet a stated RTO/RPO, tying together Phases 15 and 20.

**Task:**
1. Using the Postgres setup from the Databases phase (or a fresh one), seed a `orders` table with 1000 rows and take a `pg_dump` backup.
2. Write down a target: "RPO = 1 hour, RTO = 10 minutes" for this drill.
3. Insert 50 more rows AFTER the backup (simulating data written since the last backup — this is your RPO exposure window).
4. Start a timer. Simulate total loss: drop the database entirely.
5. Restore from the backup into a fresh database, and time how long it takes until the restored DB is queryable and verified correct (`SELECT COUNT(*)` matches the pre-drop backup count, NOT including the 50 post-backup rows — those are lost, which is the RPO cost you accepted).
6. Stop the timer. Did you beat your 10-minute RTO target? Write 2-3 sentences: if you didn't, what part of the process was slow, and what would you automate/pre-stage to fix it for next time (per the lesson's point that "untested runbooks routinely take 3-5x longer than expected under real incident pressure").

<details>
<summary>Solution / walkthrough</summary>

```bash
# seed + backup
psql -h localhost -U postgres -c "CREATE DATABASE drdrill;"
psql -h localhost -U postgres drdrill -c \
  "CREATE TABLE orders (id serial primary key, customer text);
   INSERT INTO orders (customer) SELECT 'cust-'||g FROM generate_series(1,1000) g;"

pg_dump -h localhost -U postgres -Fc drdrill > drdrill_backup.dump
```

```sql
-- simulate writes AFTER the backup — these are the RPO-exposed rows
INSERT INTO orders (customer) SELECT 'cust-post-backup-'||g FROM generate_series(1,50) g;
SELECT COUNT(*) FROM orders;   -- 1050
```

```bash
# start timer here
date

# simulate total loss
psql -h localhost -U postgres -c "DROP DATABASE drdrill;"

# restore
psql -h localhost -U postgres -c "CREATE DATABASE drdrill;"
pg_restore -h localhost -U postgres -d drdrill drdrill_backup.dump

psql -h localhost -U postgres drdrill -c "SELECT COUNT(*) FROM orders;"
# 1000 — confirms restore is correct AND confirms exactly the 50 post-backup
# rows are gone, which is your real, measured RPO cost for this drill

# stop timer here
date
```

**Sample drill writeup:**
"Restore completed in 4 minutes 12 seconds — beat the 10-minute RTO target. Data loss was exactly the 50 rows inserted after the backup, consistent with the accepted RPO window (in this drill, effectively 'since last backup,' which for a nightly-only backup schedule means up to 24 hours of real exposure — this drill only proved the restore MECHANICS work, not that the 1-hour RPO target is actually met, since the drill backup was taken seconds before the drop, not on the real nightly schedule). The slowest step was manually retyping the `pg_restore` command and checking syntax — in a real incident this should be a single pre-tested script (`./restore.sh drdrill_backup.dump`) invoked from the runbook, removing the chance of a typo under pressure being the thing that actually blows the RTO budget."

Why this matters: this drill makes the lesson's warning concrete — a backup that exists and a backup that's provably restorable inside your stated RTO are different claims, and the only way to know which one you actually have is to run the drill, time it, and write down what you'd fix.
</details>

---

## Self-Check Checklist

- [ ] Can you explain the difference between blue-green, canary, and rolling update deployments, and pick the right one for a given change (breaking schema change vs. backward-compatible feature) without hesitating?
- [ ] Can you explain what `maxSurge` and `maxUnavailable` each control, and predict pod counts mid-rollout for a given `replicas`/`maxSurge`/`maxUnavailable` combination?
- [ ] Can you explain why a broken/missing readiness probe is the #1 cause of a rolling update eating into capacity — and have you watched it happen (Lab 2, step 5)?
- [ ] Can you write a canary metrics gate (specific numbers, not "if it looks bad") for a real change?
- [ ] Can you explain why feature flags and canary/rolling deploys are complementary, not redundant — what risk does each one specifically control?
- [ ] Can you state the expand-migrate-contract pattern for a backward-incompatible DB schema change, in order, from memory?
- [ ] Can you explain RPO vs RTO well enough to translate a business requirement ("lose at most 5 min of data, back up in 30 min") into an actual infrastructure decision?
- [ ] Have you actually run a restore drill and timed it, rather than assuming your backup process works?
- [ ] Can you write a runbook using the lesson's 6-part structure (Detection → Immediate check → Likely causes → Mitigation → Escalation → Postmortem) for a real or realistic incident?
- [ ] Can you name three cost-optimization techniques from the lesson and correctly identify which ones carry real reliability risk (spot for stateful workloads) vs which are free wins (right-sizing, reserved instances for steady-state)?
