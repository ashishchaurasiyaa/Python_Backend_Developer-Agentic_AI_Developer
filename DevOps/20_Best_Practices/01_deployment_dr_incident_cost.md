# DevOps Best Practices — Deployment, DR, Incident Response & Cost
**DevOps Track · Phase 20: DevOps Best Practices**

> Deployment-strategy depth (blue-green, GitOps, SRE) already exists in `Backend_Developer/01_Year3-4_Mid/04_DevOps/13_gitops_argocd_flux.md`, `16_sre_practices_sli_slo.md`, `20_blue_green_deployment.md` — this file adds what's not covered there: canary specifics, rolling updates mechanics, feature flags, a zero-downtime checklist, disaster recovery, backup strategy, incident response structure, and cost optimization.

## Quick Concepts

- **Blue-Green Deployment** = two full environments, instant traffic switch, instant rollback
- **Canary Deployment** = gradually shift a small % of real traffic to the new version before going 100%
- **Rolling Update** = replace old instances with new ones incrementally, no big-bang cutover
- **GitOps** = Git is the source of truth; an operator reconciles cluster state to match it
- **Feature Flag** = a runtime toggle that decouples code deployment from feature release
- **Zero-Downtime Deployment** = users never see an error or dropped connection during a release
- **RPO (Recovery Point Objective)** = how much data you can afford to lose (measured in time)
- **RTO (Recovery Time Objective)** = how long you can afford to be down (measured in time)
- **3-2-1 Backup Rule** = 3 copies, 2 different media types, 1 offsite
- **Postmortem** = blameless written analysis of an incident, focused on systemic fixes
- **Spot Instance** = spare cloud capacity sold at a steep discount, can be reclaimed anytime

---

## Why This Matters

```
Writing code that works is table stakes.
Shipping it to production without breaking users, and recovering fast
when something DOES break, is what separates a backend engineer who
"can deploy" from one who OWNS production.

This phase is the difference between:
   "I pushed to main and it broke prod for 20 minutes"
   and
   "I shifted 5% of canary traffic, watched error rate for 3 minutes,
    caught the regression before it hit 100% of users, and rolled back
    with zero customer-facing impact."

That second sentence is what gets you hired at senior level.
```

---

## Blue-Green Deployment (Recap)

Full treatment: `Backend_Developer/01_Year3-4_Mid/04_DevOps/20_blue_green_deployment.md`.

```
Blue (live, v1) ◄── 100% traffic
Green (idle, v2 deployed, tested)

   Switch LB/DNS/Ingress target from Blue to Green → instant cutover
   Bug found? Switch back to Blue → instant rollback, no redeploy needed
```

Best for: breaking schema/API changes where you cannot have old and new versions serving traffic simultaneously. Cost: you run 2x the infrastructure during the switch window.

---

## Canary Deployment — Real Traffic-Shifting Example

Unlike blue-green (all-or-nothing), canary exposes a **small percentage of real production traffic** to the new version first, and you watch metrics before expanding.

```
v1 (stable) ──95%──┐
                    ├──> Load Balancer / Service Mesh ──> Users
v2 (canary)  ──5%───┘

Watch: error rate, p99 latency, business metrics (checkout success %)
   Healthy after 10 min?  → shift to 25% → 50% → 100%
   Error rate spikes?     → shift back to 0%, v2 gets zero new traffic
```

### Istio VirtualService — Weighted Traffic Split

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: orders-api
spec:
  hosts:
    - orders-api
  http:
    - route:
        - destination:
            host: orders-api
            subset: v1
          weight: 95
        - destination:
            host: orders-api
            subset: v2
          weight: 5
```

Bump `weight: 5` → `25` → `50` → `100` as each stage clears its metrics gate. Tools like **Flagger** or **Argo Rollouts** automate this stepped rollout + automatic rollback based on Prometheus queries (e.g., "roll back if `error_rate > 1%` for 2 consecutive checks").

### AWS ALB — Weighted Target Groups

```
ALB Listener Rule
   ├── Target Group: orders-api-v1   weight: 95
   └── Target Group: orders-api-v2   weight: 5
```

Configured via `aws elbv2 modify-rule` with a `forward` action listing both target groups and weights — same concept without a service mesh, useful on plain ECS/EC2 setups that don't run Istio/Linkerd.

**Canary vs Blue-Green:** canary trades a slower rollout for much lower blast radius (5% of users see a bug for 10 minutes vs 100% instantly). Use canary when you can observe good signal fast (rich metrics, decent traffic volume); use blue-green when the change is atomic/breaking and can't safely coexist with the old version at all.

---

## Rolling Updates — Kubernetes Mechanics

The **default** Kubernetes Deployment strategy — replace pods incrementally, no second environment needed.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders-api
spec:
  replicas: 10
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 2         # up to 2 EXTRA pods above desired count during rollout
      maxUnavailable: 1   # at most 1 pod below desired count during rollout
  template:
    spec:
      containers:
        - name: orders-api
          image: orders-api:v2
          readinessProbe:
            httpGet: { path: /healthz, port: 8000 }
            initialDelaySeconds: 5
            periodSeconds: 5
```

**What actually happens with `replicas: 10, maxSurge: 2, maxUnavailable: 1`:**

```
Start:        10 pods running v1
Step 1:       spin up 2 new v1→v2 pods (surge)     → 12 pods total (10 v1 + 2 v2)
Step 2:       once v2 pods pass readinessProbe,     → terminate 1 old v1 pod
              kill up to maxUnavailable old pods
Step 3:       repeat: surge more v2, retire more v1, always keeping
              (desired - maxUnavailable) pods READY and serving traffic
End:          10 pods running v2, old ones fully drained
```

- **`maxSurge`** controls how many EXTRA pods you're willing to run temporarily (costs more resources, faster rollout, less capacity risk)
- **`maxUnavailable`** controls how many pods can be missing from serving capacity at once (0 = strictest, guarantees full capacity throughout, but rollout is slower since it can only replace one-at-a-time-net)
- **The readinessProbe is what gates the whole mechanism** — Kubernetes will NOT consider a new pod "up" and won't proceed to kill an old one until the new pod's readiness probe passes. A broken or missing readiness probe is the #1 cause of a rolling update taking down capacity.
- Rolling updates are cheaper than blue-green (no full second environment) but DO run old and new versions simultaneously for the rollout duration — unsafe for breaking API/schema changes, safe for backward-compatible changes.

---

## GitOps (Recap)

Full treatment: `Backend_Developer/01_Year3-4_Mid/04_DevOps/13_gitops_argocd_flux.md`.

```
Engineer commits desired state to Git
        │
        ▼
ArgoCD/Flux (running IN the cluster) continuously diffs
actual cluster state vs Git state, and reconciles automatically
        │
        ▼
Cluster converges to match Git — Git IS the deployment
```

Pull-based (cluster pulls from Git) vs traditional CI/CD push (pipeline runs `kubectl apply`). Benefits directly relevant to this phase: every deployment is an auditable Git commit, rollback = `git revert`, and drift between "what's actually running" and "what's declared" gets auto-corrected instead of silently accumulating.

---

## Platform Engineering — Where "DevOps" Is Splitting

```
Everything in this track so far assumes ONE engineer (or a small team)
reasonably owns Docker + K8s + CI/CD + Terraform + monitoring for
their own service. That model holds at small-to-mid scale. Past a
certain org size, it breaks down: every team re-solving "how do we
get a service into prod" independently means duplicated pipelines,
inconsistent security posture, and every backend engineer needing to
be a part-time infra expert just to ship.

The 2026 industry response is PLATFORM ENGINEERING: a dedicated team
builds and maintains a self-service Internal Developer Platform (IDP)
so product/backend engineers get a paved road — "click a button, get
a new service with CI/CD, observability, and secrets already wired
up" — instead of hand-rolling infra per team. The framing you'll hear
is "platform as a product": the platform team treats OTHER engineers
as their customers, with the IDP as the product.
```

```
Backstage (open-sourced by Spotify, now a CNCF project) is the
dominant IDP tool — a service catalog + templated "golden path"
scaffolding + docs, all in one portal. Adjacent tools: Port, Cortex
(different name, unrelated to the Cortex metrics-storage project),
Humanitec.
```

**Why this belongs in your prep, not just as trivia:** at a product company, the interview question "how would DevOps practice evolve as this team grows from 10 to 200 engineers" is exactly this answer — you stop expecting every backend engineer to be a Terraform/K8s expert, and instead invest in a platform team building self-service paved roads. Naming this trend correctly (and knowing you're likely to be a **consumer** of an IDP as a backend engineer, not necessarily its builder, unless you specifically pivot into platform engineering) signals you're tracking where the industry is heading, not just where it's been.

---

## Feature Flags — Decoupling Deploy from Release

**The core idea:** ship code to production behind a flag that's OFF, so deployment and release become two separate decisions. This means you can deploy Friday afternoon (the code path is dark/inert) and release Monday morning (flip the flag) without a redeploy.

```python
from launchdarkly import LDClient  # or Unleash, or a homegrown flag service

client = LDClient(sdk_key=settings.LD_SDK_KEY)

def get_checkout_flow(user):
    if client.variation("new-checkout-flow", user, default=False):
        return NewCheckoutFlow()
    return LegacyCheckoutFlow()
```

**Homegrown flag pattern (when you don't want a SaaS dependency):** a `feature_flags` table/Redis hash keyed by flag name → `{enabled: bool, rollout_percent: int, allowed_user_ids: [...]}`, checked at request time, cached with a short TTL so a flag flip propagates within seconds without a deploy.

```python
def is_enabled(flag_name: str, user_id: int) -> bool:
    flag = cache.get_or_set(f"flag:{flag_name}", lambda: db.get_flag(flag_name), ttl=30)
    if not flag.enabled:
        return False
    if user_id in flag.allowed_user_ids:
        return True
    return (user_id % 100) < flag.rollout_percent   # sticky percentage rollout
```

**Real tools:** LaunchDarkly and Unleash (open-source) are the standard picks; both support percentage rollouts, user targeting, and kill-switches. Full experimentation-focused depth (A/B testing tie-in): `Backend_Developer/01_Year3-4_Mid/04_DevOps/18_feature_flags_experimentation.md`.

**DevOps angle:** feature flags are your fastest rollback mechanism — flipping a flag is milliseconds, a redeploy is minutes. Any high-risk feature launch should ship dark first, then ramp via flag, with canary/rolling deployment handling the CODE risk and the flag handling the FEATURE risk — they're complementary, not substitutes for each other.

---

## Zero-Downtime Deployment Checklist

```
[ ] Health checks configured and ACCURATE
      - Liveness probe: is the process alive? (restart if not)
      - Readiness probe: can it serve traffic RIGHT NOW?
        (must check DB connectivity, not just "process is running")

[ ] Readiness probe gates traffic BEFORE the pod/instance joins the LB pool
      - New instance registers with LB only after passing readiness
      - Old instance deregisters from LB BEFORE it's killed, not after

[ ] Connection draining / graceful shutdown
      - On SIGTERM: stop accepting NEW connections,
        finish IN-FLIGHT requests (typically 15-30s grace period),
        THEN exit
      - K8s: terminationGracePeriodSeconds must exceed your
        longest reasonable request duration
      - LB: deregistration delay must allow in-flight requests to drain
        before the instance is forcibly removed

[ ] Database migrations are BACKWARD COMPATIBLE with the old code
      - Never: deploy code that requires a column the migration
        hasn't run yet (or vice versa)
      - Pattern: expand → migrate → contract
        1. Add new column (nullable) — deploy — old code ignores it
        2. Deploy new code that writes to BOTH old and new columns
        3. Backfill existing rows
        4. Deploy code that reads from new column only
        5. Drop old column (separate deploy, after full confidence)

[ ] Correct deploy ORDER for breaking API changes
      - Backward-compatible API changes only during rolling updates
        (old and new pods serve simultaneously)
      - Breaking changes need blue-green or a versioned API
        (/v1/orders and /v2/orders coexisting)

[ ] Rollback plan tested BEFORE you need it
      - Can you roll back in under 5 minutes? Have you actually
        practiced it, or just assumed `kubectl rollout undo` works?

[ ] Session/state handled externally
      - No in-memory session state on the instance being killed
        (sticky sessions + rolling deploy = dropped user sessions)
```

---

## Disaster Recovery — RPO vs RTO

| | RPO (Recovery Point Objective) | RTO (Recovery Time Objective) |
|---|---|---|
| **Question it answers** | "How much data can we afford to lose?" | "How long can we afford to be down?" |
| **Measured from** | Time since last good backup/replica | Time from failure to full recovery |
| **Driven by** | Backup/replication frequency | Automation, runbook quality, failover speed |

**Worked example:** an e-commerce order database.

```
Business requirement: "We can lose at most 5 minutes of orders,
                        and must be back online within 30 minutes."

   → RPO = 5 minutes  → need continuous/near-continuous replication
     (async replica with <5 min lag, or transaction log shipping
      every ≤5 min — a nightly backup alone gives RPO = 24 hours,
      which fails this requirement)

   → RTO = 30 minutes → need automated failover, not "wait for an
     engineer to wake up and restore from S3." This means:
     - Multi-AZ RDS with automated failover (~1-2 min), or
     - A warm standby you can promote via a scripted runbook,
       tested regularly (untested runbooks routinely take 3-5x
       longer than expected under real incident pressure)
```

Tighter RPO/RTO = more expensive infrastructure (synchronous replication, warm/hot standbys, multi-region active-active). The business requirement should drive the spend, not the other way around — don't over-engineer a 4-hour RTO system for an internal admin tool that nobody notices is down for a day.

---

## Backup & Restore — The 3-2-1 Rule

```
3 copies of your data total (production + 2 backups)
2 different storage media/systems (not two backups on the same disk/account)
1 copy offsite (different region/provider — protects against a
  regional outage, a compromised account, or a ransomware event
  that encrypts everything reachable from one set of credentials)
```

**Practical AWS example:**
1. Production: RDS Postgres in `ap-south-1`
2. Copy 2: automated RDS snapshots (same region, different "system" — S3-backed, not the live volume)
3. Copy 3 (offsite): cross-region snapshot copy to `us-east-1`, or `pg_dump` exported nightly to a separate S3 bucket in a different account (blast-radius isolation from a compromised primary account)

**Non-negotiable practice:** untested backups are a hypothesis, not a backup. Run a scheduled restore drill (monthly/quarterly) into a scratch environment and verify the app actually boots against the restored data — "the snapshot exists" and "the snapshot is restorable and correct" are different claims.

---

## Incident Response

### Severity Levels (typical scheme)

| Sev | Definition | Example | Response |
|---|---|---|---|
| **SEV1** | Full outage or data loss, all users affected | Site down, payments failing for everyone | Page immediately, all-hands, exec notified |
| **SEV2** | Major feature broken, subset of users affected | Checkout broken for one payment provider | Page on-call, dedicated incident channel |
| **SEV3** | Degraded but functional, workaround exists | Search is slow but works | Ticket, fix in next business day |
| **SEV4** | Cosmetic/minor | Typo in an email template | Backlog |

### Runbook Structure

```
1. Detection      — how the alert fires (Prometheus alert, PagerDuty)
2. Immediate check — dashboard link, "is this a false alarm" quick test
3. Likely causes   — ranked list from past incidents ("check X first, it's
                      caused this 60% of the time")
4. Mitigation      — concrete commands: rollback command, feature-flag
                      kill switch, scale-up command, failover command
5. Escalation path — who to page next if mitigation doesn't work, in what order
6. Postmortem      — link to template, mandatory within 48h for SEV1/SEV2
```

### Blameless Postmortems

- Focus on **systemic** causes ("the alert threshold was too high," "the runbook was outdated," "we had no canary stage") not **individual blame** ("Ashish pushed bad code")
- Structure: timeline of events → what went well → what went wrong → root cause (5-whys) → action items with OWNERS and DUE DATES
- The goal is that the SAME failure mode cannot recur silently — action items should be tracked as real tickets, not just documented and forgotten

---

## Cost Optimization

| Technique | What it does | When to use |
|---|---|---|
| **Reserved Instances / Savings Plans** | Commit to 1-3yr usage for 30-70% discount vs on-demand | Baseline, predictable, always-on capacity (your steady-state web/API tier) |
| **Spot Instances** | Spare capacity at 60-90% discount, can be reclaimed with ~2 min warning | Stateless, fault-tolerant, interruptible workloads — batch jobs, CI runners, non-critical worker pools; NEVER your primary database or the only replica of a stateful service |
| **Right-Sizing** | Match instance type to actual CPU/memory usage, not "just pick the popular size" | Ongoing — review CloudWatch/Prometheus utilization monthly; an `m5.2xlarge` running at 8% CPU is money on fire |
| **S3 Lifecycle Tiers** | Auto-transition objects to cheaper storage classes as they age | Logs, backups, old uploads — see below |
| **Autoscaling to zero (where possible)** | Scale non-prod/dev environments down outside business hours | Staging, dev, QA environments running 24/7 for no reason |

### S3 Lifecycle Tiers — Real Example

```
Day 0-30:    S3 Standard           (frequent access — recent logs, active reports)
Day 30-90:   S3 Standard-IA        (infrequent access, ~45% cheaper, small retrieval fee)
Day 90-365:  S3 Glacier Instant Retrieval  (rarely accessed, big storage discount)
Day 365+:    S3 Glacier Deep Archive      (compliance-only retention, cheapest tier,
                                            retrieval takes hours)
Day 2555 (7yr): Delete             (per compliance/retention policy)
```

```json
{
  "Rules": [{
    "ID": "log-lifecycle",
    "Status": "Enabled",
    "Filter": { "Prefix": "logs/" },
    "Transitions": [
      { "Days": 30, "StorageClass": "STANDARD_IA" },
      { "Days": 90, "StorageClass": "GLACIER_IR" },
      { "Days": 365, "StorageClass": "DEEP_ARCHIVE" }
    ],
    "Expiration": { "Days": 2555 }
  }]
}
```

Ties back to Phase 7 (Cloud/AWS) — this is the kind of policy you configure once via Terraform (Phase 8) and it silently saves real money forever, which is exactly the kind of cost-conscious detail interviewers probe for at senior level.

---

## Senior Tip

```
Cost optimization and reliability are usually framed as opposites,
but the senior move is knowing WHERE they don't conflict:

   - Spot instances for CI runners: cheaper AND doesn't touch reliability
     (a failed CI job just retries)
   - Right-sizing: cheaper AND often improves reliability
     (an over-provisioned instance hides a memory leak until it's
      finally under real pressure)
   - Reserved instances for your steady-state tier: cheaper AND
     zero reliability tradeoff (you were running that capacity anyway)

Only autoscaling non-prod to zero and spot for STATEFUL workloads
carry real risk — know the difference, and you'll sound like someone
who's actually owned a cloud bill, not just read about it.
```

## Interview Angle

**Q: "Walk me through deploying a breaking database schema change with zero downtime."**

Strong answer: expand/contract pattern (add nullable column → deploy dual-write code → backfill → deploy read-from-new code → drop old column in a later deploy), each step is its own deployment gated by a rolling update or canary with health checks, feature flag to instantly disable the new code path if backfill or dual-write reveals a bug, and a tested rollback plan at every step — never a single "deploy schema change + code change together" step, because that's the change you can't safely half-roll-back if the rollout goes bad.

---

## Related

- [`Backend_Developer/01_Year3-4_Mid/04_DevOps/13_gitops_argocd_flux.md`](../../Backend_Developer/01_Year3-4_Mid/04_DevOps/13_gitops_argocd_flux.md) — GitOps depth
- [`Backend_Developer/01_Year3-4_Mid/04_DevOps/16_sre_practices_sli_slo.md`](../../Backend_Developer/01_Year3-4_Mid/04_DevOps/16_sre_practices_sli_slo.md) — SLI/SLO/error budgets, MTTR
- [`Backend_Developer/01_Year3-4_Mid/04_DevOps/18_feature_flags_experimentation.md`](../../Backend_Developer/01_Year3-4_Mid/04_DevOps/18_feature_flags_experimentation.md) — feature flags + A/B testing depth
- [`Backend_Developer/01_Year3-4_Mid/04_DevOps/20_blue_green_deployment.md`](../../Backend_Developer/01_Year3-4_Mid/04_DevOps/20_blue_green_deployment.md) — blue-green depth
- [`../19_Observability/01_metrics_logs_traces_opentelemetry.md`](../19_Observability/01_metrics_logs_traces_opentelemetry.md) — the signals that gate every canary/rollout decision above
- [`../21_Projects/README.md`](../21_Projects/README.md) — project 9 (Blue-Green) and project 2 (CI/CD) put this into practice
