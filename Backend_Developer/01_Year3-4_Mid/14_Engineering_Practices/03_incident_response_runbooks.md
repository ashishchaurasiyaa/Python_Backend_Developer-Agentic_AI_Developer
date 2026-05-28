# 🚨 Incident Response & Runbooks — Architecture Guide

> **Target:** 3-4 YOE | **Goal:** Production down hai, kya karna hai. On-call ka mindset. Senior-level skill.

---

## Part 1: WHAT — Incident Kya Hai?

### Definition

> **Incident** = unplanned event jo production system me **service degradation** ya **outage** cause kare.

### Severity Levels

```
SEV-1 (P0): Total outage. Customers can't use product. PANIC.
SEV-2 (P1): Major feature broken. Many customers affected.
SEV-3 (P2): Minor feature broken. Few customers affected.
SEV-4 (P3): Cosmetic issue. No business impact.
```

### Real-Life Analogy 🔥

Soch tu **building manager** hai apartment complex me:
- Fire alarm = SEV-1
- Elevator stuck = SEV-2
- Tap leaking = SEV-3
- Paint peeling = SEV-4

Different responses, different urgency.

---

## Part 2: WHY — Incident Response Critical?

### Reason 1: Customer Trust

> **5 minutes downtime = thousands of customer complaints + lost trust.** Big platforms (FB, Google) downtime news ban jaata hai.

### Reason 2: Revenue Loss

```
E-commerce site:
- $10,000/minute revenue normal
- Downtime: 1 hour
- Lost revenue: $600,000
```

Real number. Real impact.

### Reason 3: SLA Penalties

Contracts with enterprise customers:
- "99.9% uptime guaranteed"
- Failure = refunds, penalties

### Reason 4: Career Impact

How you handle incidents = visibility to leadership.
**Senior promotion often hinges on incident handling.**

### Reason 5: System Improvement

Each incident = learning. Post-mortem fixes systemic issues.

---

## Part 3: HOW — Incident Response Architecture

### The Lifecycle

```
DETECTION → TRIAGE → MITIGATION → RESOLUTION → POSTMORTEM → FIX
```

### Detailed Flow

```
┌─────────────────────────────────────────┐
│  1. DETECTION                            │
│  - Alert fires (Prometheus/Datadog)     │
│  - Customer reports                     │
│  - On-call notified via PagerDuty       │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  2. TRIAGE                              │
│  - What's broken?                       │
│  - How bad?                             │
│  - Who's affected?                      │
│  - Set severity                         │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  3. MITIGATION (Stop the bleeding)      │
│  - Roll back deploy                     │
│  - Disable feature flag                 │
│  - Restart service                      │
│  - Scale up                             │
│  Goal: Restore service ASAP             │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  4. RESOLUTION                          │
│  - Service back to normal               │
│  - Customers OK                         │
│  - Monitor for recurrence               │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  5. POSTMORTEM                          │
│  - What happened?                       │
│  - Why?                                 │
│  - How to prevent?                      │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  6. FIX (Long-term)                     │
│  - Add monitoring                       │
│  - Fix root cause                       │
│  - Update runbook                       │
└─────────────────────────────────────────┘
```

---

## Part 4: On-Call Mindset

### When Pager Goes Off at 3 AM

**Do NOT:**
- Panic
- Code immediately
- Speculate randomly

**DO:**
- Calm down (deep breath)
- Read alert carefully
- Open laptop
- Follow runbook

### The Calm Investigator Mindset

> **Be Sherlock Holmes, not panicked surgeon.** Facts first, action second.

---

## Part 5: Runbooks — Pre-Written Recovery Plans

### What is a Runbook?

> **Step-by-step guide** for handling a specific incident type. **Written when calm, used when panicking.**

### Real-Life Analogy 📖

Pilot's emergency checklist:
- Engine failure: do A, B, C, D
- Fire onboard: do X, Y, Z

Tested, proven. **No improvisation in crisis.**

### Runbook Structure

```
RUNBOOK: Database Connection Pool Exhausted

## Symptoms
- 503 errors increasing
- "Connection pool exhausted" in logs
- DB metrics show max connections

## Severity
SEV-2 (major degradation)

## Quick Mitigation (DO FIRST)
1. Restart backend pods (kubectl rollout restart)
2. Verify connection count drops
3. Monitor for 5 minutes

## Investigation
1. Check recent deploys
2. Look for slow queries
3. Check connection leak

## Root Cause Possibilities
- Long-running queries
- Missing connection.close()
- Traffic spike
- Pool size too small

## Long-term Fixes
- Add connection pool monitoring
- Set query timeout
- Increase pool size

## Related Alerts
- DB CPU high
- API latency high

## Escalation
On-call → Tech lead → Engineering manager
```

---

## Part 6: Common Runbooks Every Team Should Have

### 1. High Latency

```
Check:
- Database slow queries
- External API timeouts
- Memory pressure
- CPU saturation
```

### 2. High Error Rate

```
Check:
- Recent deploys (rollback?)
- Database connection
- Third-party services
- Bad config
```

### 3. Database Issues

```
Check:
- Connection count
- Replication lag
- Disk space
- Slow queries
```

### 4. Memory Leak

```
Check:
- Process memory growing
- Long-running connections
- Cache size
- File descriptors
```

### 5. Disk Full

```
Mitigation:
- Delete old logs
- Compress files
- Scale up disk
- Find rogue process
```

### 6. SSL Certificate Expired

```
Mitigation:
- Renew immediately (Let's Encrypt)
- Update DNS if needed
- Verify renewal automation
```

### 7. DDoS Attack

```
Mitigation:
- Cloudflare/WAF protection
- Rate limiting
- Block malicious IPs
- Scale infrastructure
```

### 8. Bad Deploy

```
Mitigation:
- Rollback immediately
- Investigate after restored
- Update tests to catch
```

---

## Part 7: Severity Decision Tree

```
Service Down?
├─ Yes → Customers can't use product?
│        ├─ Yes → SEV-1
│        └─ No → SEV-2
└─ No → Degradation?
         ├─ Major (50%+ affected) → SEV-2
         ├─ Minor (<50% affected) → SEV-3
         └─ Cosmetic → SEV-4
```

### Quick Decision Test

> "Would you wake up CEO at 3 AM?"
- Yes → SEV-1
- Maybe → SEV-2
- No → SEV-3+

---

## Part 8: First 10 Minutes of an Incident

### The Speedrun

```
Minute 1: Acknowledge alert
Minute 2: Read alert, check dashboard
Minute 3: Determine severity
Minute 4: Notify team (Slack channel)
Minute 5: Open runbook
Minute 6-10: Execute mitigation
```

### Communication is Critical

```
Slack #incidents:
"🚨 SEV-2 incident: API errors elevated to 5%
Investigating. Will update in 10 min."
```

**Update every 15-30 minutes** until resolved.

---

## Part 9: The Incident Commander Role

### What is IC?

> **One person who coordinates the response.** Not the one fixing, but coordinating.

### IC Responsibilities

- Set severity
- Assign roles
- Communicate to stakeholders
- Make decisions (rollback or not)
- Track timeline
- Coordinate hand-offs

### Why Need IC?

5 people debugging same thing = chaos.
1 IC + 4 specialists = focused.

---

## Part 10: Communication During Incident

### Internal Communication

#### Slack Channel: #incident-xyz

```
14:32 - Alerts firing for high error rate
14:34 - Investigating, looking at logs
14:38 - Root cause likely bad deploy
14:40 - Initiating rollback
14:45 - Rollback complete, errors decreasing
14:50 - Confirmed resolved
14:52 - Closing incident
```

**Timestamps important** for post-mortem.

### Status Page (Public)

```
🟡 INVESTIGATING — Some users may experience slowness
Posted: 14:32 IST

Update: 14:50 — Issue identified, fix in progress
Update: 15:10 — Resolved. Monitoring.
```

**Honesty wins trust.**

### Stakeholder Updates

Email/Slack to:
- Customer success (they handle customer complaints)
- Leadership
- Sales (if affects deals)
- PR (if SEV-1)

---

## Part 11: Mitigation Strategies

### Strategy 1: Rollback (Most Common)

> **Latest deploy caused issue → revert to previous version.**

```
kubectl rollout undo deployment/api
```

Fast, proven, safe.

### Strategy 2: Feature Flag Off

> **Bad feature → toggle off without deploy.**

If you have feature flags, this is fastest.

### Strategy 3: Scale Up

> **Traffic spike → add more servers.**

```
kubectl scale deployment/api --replicas=20
```

### Strategy 4: Restart Service

> **Memory leak / weird state → restart.**

"Have you tried turning it off and on again?" works in prod too.

### Strategy 5: Block Bad Traffic

> **Bot/attack → block at WAF.**

### Strategy 6: Fail Over

> **Primary DB dead → switch to replica.**

### Strategy 7: Degrade Gracefully

> **Some features down → return partial response, not error.**

---

## Part 12: Post-Mortem Process (Brief — see other doc)

### After Resolution

1. **Wait 24 hours** — emotions settle
2. **Schedule meeting** — within 1 week
3. **Blameless mindset** — focus on systems
4. **Document everything** — public to org
5. **Action items** — assign owners, due dates
6. **Follow up** — close action items

---

## Part 13: Incident Severity Examples

### SEV-1 Examples

- Entire site down (500 errors)
- Database completely unavailable
- Data loss occurring
- Security breach in progress
- Customer money lost

### SEV-2 Examples

- 50% of users can't log in
- Payment system slow (8 sec response)
- Search broken (other features OK)
- Specific region down

### SEV-3 Examples

- One feature broken (others fine)
- Old API version errors
- Slow page (still works)
- 10% users affected

### SEV-4 Examples

- Typo on website
- Slight UI misalignment
- Minor cosmetic
- Non-production bug

---

## Part 14: Tools You'll Use

### Alerting
- **PagerDuty** — most popular
- **OpsGenie** — Atlassian's
- **VictorOps** — Splunk's

### Monitoring
- **Datadog** — comprehensive
- **New Relic** — APM
- **Prometheus + Grafana** — open source
- **CloudWatch** — AWS native

### Logging
- **ELK Stack** (Elasticsearch + Logstash + Kibana)
- **Splunk** — enterprise
- **Loki** — Grafana's

### Tracing
- **Jaeger**
- **OpenTelemetry**
- **AWS X-Ray**

### Status Pages
- **Statuspage.io**
- **Better Uptime**
- **Cachet**

### Incident Management
- **incident.io**
- **FireHydrant**
- **Rootly**

---

## Part 15: Pre-Incident Preparation

### What to Have Ready

#### 1. Runbooks
For top 10 incident types. Tested.

#### 2. Dashboards
- Service health overview
- Latency, error rate, RPS
- Database metrics
- Infrastructure metrics

#### 3. Logs Access
- Centralized logging
- Quick search
- Last 30 days minimum

#### 4. Incident Channel Template
Slack channel + topic + pinned messages.

#### 5. Rollback Capability
- Last 5 deploys deployable
- Database migration rollback plan
- Feature flag system

#### 6. Communication Templates
- Internal Slack
- External status page
- Customer email

#### 7. Contact List
- All engineers' phone
- Vendor support numbers
- Executive escalation

---

## Part 16: On-Call Best Practices

### Rotation Policy

```
1 week on-call
Then 5 weeks off
Pair on-call (primary + secondary)
```

### Compensation

> **On-call is work.** Compensate fairly:
- Extra pay per shift
- Time off after carrying
- Recognition

### Boundaries

- **Sleep when on-call**: laptop bedside
- **Notify partner/family**: explain pager
- **Don't drink heavily**: stay sober
- **Plan activities**: but be reachable

### Hand-Off

End of shift, hand off to next on-call:
- Active issues
- Recent changes
- Watch items

---

## Part 17: Anti-Patterns

### Anti-Pattern 1: Hero Culture

> "Bhai is the only one who can fix this."

Bad! Everyone should be able to handle. Spread knowledge.

### Anti-Pattern 2: Blame Game

> "Who deployed this?"

Bad! Blameless culture. Systems fail, not people.

### Anti-Pattern 3: No Documentation

> "It's all in Bhai's head."

Bad! Document everything.

### Anti-Pattern 4: Alert Fatigue

> 100 alerts/day, mostly false positives.

Bad! Tune alerts. Quality over quantity.

### Anti-Pattern 5: Skipping Postmortems

> "We fixed it, move on."

Bad! Postmortems prevent next incident.

### Anti-Pattern 6: Production Debugging

> Logging into prod, running queries.

Bad! Read replicas, log analysis, observability tools.

---

## Part 18: The 5 Whys

### Root Cause Analysis Technique

Ask "Why?" 5 times.

```
Q: Why did the site go down?
A: Database crashed.

Q: Why did database crash?
A: Connection pool exhausted.

Q: Why was pool exhausted?
A: New feature opened connections without closing.

Q: Why didn't tests catch this?
A: Tests don't simulate high concurrency.

Q: Why don't we have load tests?
A: Never prioritized.

ROOT CAUSE: Lack of load testing
ACTION: Add load tests to CI
```

---

## Part 19: Incident Drills

### Practice Makes Perfect

> **Pilots practice emergencies. So should engineers.**

#### Chaos Engineering

> Intentionally break things to test resilience.

- Kill a random server
- Drop database
- Slow network
- See what happens

#### Game Days

Scheduled drills:
1. Pick a scenario
2. Run it in staging
3. Have team respond
4. Debrief

**Netflix's Chaos Monkey** — famous example.

---

## Part 20: Bhai's Personal Incident Checklist

```
Pre-incident:
□ Runbooks updated
□ Dashboards accessible
□ Team contacts current
□ Backups verified

During incident:
□ Acknowledge alert (5 min max)
□ Assess severity
□ Open Slack channel
□ Follow runbook
□ Communicate every 15 min
□ Time-stamp everything
□ Roll back if uncertain
□ Mitigate, then investigate

Post-incident:
□ Verify fully resolved
□ Update status page
□ Close incident channel
□ Schedule postmortem
□ Document timeline
□ Get sleep
```

---

## Part 21: Q&A

### Q: When to escalate?
**A**: When stuck for 15-20 min, when SEV-1, when need help.

### Q: Should I roll back if not 100% sure?
**A**: Yes. Mitigate first. Investigate later.

### Q: What if I caused the incident?
**A**: Hide nothing. Be transparent. Blameless culture.

### Q: Customer asks "what happened?"
**A**: Honest, brief, professional. "We had an issue with X. It's resolved. Apologies."

### Q: When can I sleep on-call?
**A**: When no active incident. Set high-volume alerts only for SEV-1/2.

### Q: Burning out from on-call?
**A**: Talk to manager. Adjust rotation. Improve runbooks. Reduce alert noise.

---

## 🎯 Bhai's Final Words

> **On-call is the most stressful, most rewarding part of senior engineering. Calm in crisis = senior superpower.**

3 Rules:
1. **Mitigate first** (restore service)
2. **Investigate after** (find root cause)
3. **Improve always** (postmortem actions)

Production incidents will happen. **Question is — how prepared are you?** 🚀
