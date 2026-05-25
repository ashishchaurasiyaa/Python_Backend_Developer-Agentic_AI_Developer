# 14 — Chaos Engineering

> Deliberately break production in controlled ways to discover weaknesses before users do. Pioneered by Netflix.

---

## Why Chaos Engineering

Modern distributed systems fail in unpredictable ways:
- A new dependency goes down.
- Network partition for 30 sec.
- Disk fills on one replica.
- DNS hiccup.

You can't anticipate all failure modes. So: cause failures intentionally, see what breaks, fix it.

**Famous quote (Netflix):** "The best way to avoid failure is to fail constantly."

---

## Principles

### 1. Build a hypothesis
"If we kill 1 of 3 API pods, error rate stays < 0.1%."

### 2. Define steady state
What's normal? Latency p99 < 200ms, error rate < 0.5%.

### 3. Run experiment
Inject the failure (kill pod, slow network, etc.).

### 4. Verify hypothesis
Did steady state hold?

### 5. Learn & improve
Document findings. Fix gaps. Repeat.

---

## Failure Categories

### Resource
- CPU saturation.
- Memory exhaustion.
- Disk full.
- Network bandwidth saturation.

### State / Process
- Pod crashes.
- Container restart loops.
- Kernel panics.

### Network
- Packet loss.
- Latency injection.
- DNS failure.
- TLS errors.
- Port blocks.

### Dependency
- DB unavailable.
- Cache unavailable.
- Third-party API slow / 500.

### Time
- Clock skew.
- Time jumps.

---

## Tools

### Chaos Monkey (Netflix, original)
Kills random VMs in your cluster during business hours.

### LitmusChaos
Kubernetes-native. CRDs for chaos experiments.

```yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: api-pod-delete
spec:
  appinfo:
    appns: prod
    applabel: app=api
    appkind: deployment
  experiments:
    - name: pod-delete
      spec:
        components:
          env:
            - name: TOTAL_CHAOS_DURATION
              value: "60"
            - name: PODS_AFFECTED_PERC
              value: "33"
```

### Chaos Mesh
Similar to Litmus. By PingCAP.

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: delay-prod
spec:
  action: delay
  mode: one
  selector:
    namespaces: [prod]
    labelSelectors:
      app: api
  delay:
    latency: "100ms"
    jitter: "10ms"
  duration: "5m"
```

### Gremlin
Commercial chaos engineering platform. Strong UI.

### Chaostoolkit
Python-based open source CLI.

```yaml
version: 1.0.0
title: API resilient to one pod kill
description: Verify health stays during pod loss
steady-state-hypothesis:
  title: API responding
  probes:
    - name: api-healthy
      type: probe
      tolerance: 200
      provider:
        type: http
        url: https://api.example.com/health
method:
  - type: action
    name: kill-one-pod
    provider:
      type: process
      path: kubectl
      arguments: ["delete", "pod", "-l", "app=api", "--all"]
```

### AWS Fault Injection Simulator
AWS-native. Inject EC2 stops, EBS pauses, RDS failovers.

---

## Game Days

Scheduled chaos exercises with the team present.

### Format
1. Define scenario: "What if cache cluster is unreachable?"
2. Team predicts outcome.
3. Inject failure (e.g., DROP cache pods).
4. Observe.
5. Recover.
6. Debrief: what worked, what didn't, action items.

### Frequency
- Quarterly for novice teams.
- Monthly for mature teams.
- Continuous (automated) for advanced.

---

## Specific Experiments

### Experiment 1: Kill a pod
```bash
kubectl delete pod -l app=api --all --grace-period=0 --force
```

Expected: HPA / replicas absorb load; brief 5xx spike but recovery in seconds.

### Experiment 2: CPU stress
```bash
kubectl exec api-pod -- stress --cpu 8 --timeout 60
```

Expected: requests slow, HPA scales up. p99 latency spikes but error rate stable.

### Experiment 3: Network latency
```bash
# tc (traffic control) injects latency
tc qdisc add dev eth0 root netem delay 200ms
sleep 60
tc qdisc del dev eth0 root
```

Expected: client timeouts, but circuit breaker opens, fallback used.

### Experiment 4: DNS failure
```bash
# Add bad DNS entry
iptables -A OUTPUT -p udp --dport 53 -j DROP
```

Expected: connection failures; service mesh sidecar handles or retries.

### Experiment 5: DB connection exhaustion
```bash
# Fill connection pool from chaos pod
for i in {1..200}; do (psql -c "SELECT pg_sleep(60)" &); done
```

Expected: pool exhaustion → 503 to clients with proper backpressure messaging.

### Experiment 6: Slow downstream
```yaml
# Inject 5sec latency to all calls to payment-svc
NetworkChaos: delay 5s for label=app=payment-svc
```

Expected: API circuit breaker opens for payment-svc; user sees "service unavailable" message, not infinite spinner.

---

## Production vs Pre-Production

### Pre-production chaos
- Safe to crash everything.
- Easier to start here.
- Lower fidelity (different scale than prod).

### Production chaos
- Only on small subset (e.g., 1% of traffic).
- Have rollback ready.
- Run during low-traffic hours initially.
- Monitor user impact in real-time.
- Stop if SLOs violated.

Most teams: pre-prod chaos first, then graduate to prod.

---

## Building Resilience (Outcomes)

After chaos experiment fails, fix root cause:

### Pod kills cause errors → Implement
- Multiple replicas.
- Pod disruption budget.
- Health checks tuned.
- Graceful shutdown.

### Downstream slow → Implement
- Circuit breakers.
- Timeouts everywhere.
- Bulkheads (separate thread pools per dependency).
- Fallback responses.

### Cache unavailable → Implement
- Cache-aside with DB fallback.
- Stampede protection.
- Stale-while-revalidate.

### DB primary fails → Implement
- Read from replicas during failover.
- Connection retry with backoff.
- Async writes (queue + DB write).

### Region outage → Implement
- Multi-region active-active.
- DNS failover.
- Data replication.

---

## Service Mesh + Chaos

Istio / Linkerd let you inject failures via config:

```yaml
# Inject 5sec delay 30% of the time
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: api
spec:
  http:
  - fault:
      delay:
        percentage:
          value: 30
        fixedDelay: 5s
    route:
    - destination:
        host: api
```

```yaml
# Inject 50% error rate
spec:
  http:
  - fault:
      abort:
        percentage:
          value: 50
        httpStatus: 500
    route:
    - destination:
        host: api
```

No app code changes; toggle via config.

---

## Common Pitfalls

### 1. Chaos without observability
You inject failure but can't see what broke. Always have logging + metrics + tracing in place first.

### 2. Chaos without consent
Run experiments without team awareness → panic during real incident.

### 3. Chaos when on-call team unavailable
Schedule chaos with eng team available.

### 4. Skipping post-mortem
Just running chaos isn't enough. Document findings.

### 5. Running unbounded
Auto-rollback after fixed duration. Never leave chaos running indefinitely.

### 6. No blast radius limit
1% chaos → 100%. Always limit scope.

---

## Maturity Levels

| Level | What |
|---|---|
| 1 | Manual game days in pre-prod |
| 2 | Scripted chaos in pre-prod |
| 3 | Automated chaos in pre-prod |
| 4 | Manual chaos in prod (during low-traffic) |
| 5 | Automated continuous chaos in prod |

Most teams: levels 1-2. Top teams (Netflix, Amazon): level 5.

---

## SRE Practices Alongside

### Error budgets
Per SLO: how much error / latency budget you have monthly.
- Within budget → free to do risky deploys + chaos.
- Over budget → freeze releases.

### Blameless post-mortems
After incidents (chaos-induced or real), focus on system fixes, not who-screwed-up.

### Runbooks
Document common failures + responses. Reduce on-call cognitive load.

---

## Cost of Chaos

- Engineer time (small for occasional).
- Risk of real user impact (mitigated by blast-radius limits).
- Tooling (most OSS; commercial Gremlin $$).

ROI:
- Production incidents discovered in chaos: cheap to fix.
- Same incidents discovered in production crisis: 10-100x cost in lost revenue + emergency response.

---

## Real-World Stories

### Netflix
Chaos Monkey runs daily. Discovered hundreds of resilience gaps over years.

### AWS
Tests AZ failovers regularly. Used to bring down full AZs in private tests.

### Slack
Public post-mortems show extensive chaos engineering practices.

### Cloudflare
Runs failover drills monthly. Practices regional outage scenarios.

---

## Getting Started Checklist

```
☐ Set up observability (metrics, logs, traces).
☐ Define SLOs for critical services.
☐ Run first game day in staging.
☐ Document findings.
☐ Fix top 3 issues.
☐ Repeat with new scenarios.
☐ Graduate to prod chaos (small blast radius).
☐ Automate common experiments.
```

---

## TL;DR

- Chaos = deliberate failure to discover weaknesses.
- Tools: LitmusChaos, Chaos Mesh, Gremlin, Chaostoolkit.
- Start with pre-prod game days.
- Always have observability + rollback.
- Limit blast radius (1% of traffic).
- Document + fix findings.
- Outcome: more resilient system, calmer on-call.
- Mature orgs do this continuously.
