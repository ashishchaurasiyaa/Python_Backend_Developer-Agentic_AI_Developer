# 📝 Post-Mortem Writing — Architecture Guide

> **Target:** 3-4 YOE | **Goal:** Blameless post-mortem kaise likhe — template, mindset, follow-through.

---

## Part 1: WHAT — Post-Mortem Kya Hai?

### Definition

> **Post-mortem** = incident ke baad ka **written analysis**: kya hua, kyu hua, kya seekha, kaise prevent karenge.

### Real-Life Analogy 🏥

Hospital me **death audit** hota hai:
- Patient kaise mara?
- Kya prevent ho sakta tha?
- Doctor ne kya alag karna chahiye tha?
- Process improve kaise karein?

**No blame, just learning.** Yahi post-mortem hai.

---

## Part 2: WHY — Post-Mortem Critical Kyu?

### Reason 1: Prevent Repeat Issues

Same bug 2nd time = "did we learn nothing?"
Post-mortem = systematic prevention.

### Reason 2: Knowledge Spread

Whole team learns from one incident. **One person's mistake = team's lesson.**

### Reason 3: System Improvement

Reveals weaknesses:
- Missing monitoring
- Poor runbooks
- Inadequate testing

### Reason 4: Blameless Culture

Without post-mortem culture, people hide issues. With it, transparency wins.

### Reason 5: Compliance

Some industries (finance, healthcare) require incident reports.

---

## Part 3: HOW — Post-Mortem Process

### The Lifecycle

```
INCIDENT RESOLVED
       │
       │ 24-48 hours
       ▼
DRAFT POST-MORTEM
(by incident commander)
       │
       │ 24 hours
       ▼
TEAM REVIEW MEETING
(blameless discussion)
       │
       │
       ▼
FINAL DOCUMENT
(published org-wide)
       │
       │
       ▼
ACTION ITEMS
(assigned, tracked)
       │
       │ Weeks/months
       ▼
ITEMS COMPLETED
(close the loop)
```

---

## Part 4: The Blameless Principle

### What "Blameless" Means

> **Focus on systems and processes, not individuals.**

### Bad Post-Mortem (Blameful)

```
"Bhai deployed bad code without testing.
Bhai should be more careful.
Bhai will not deploy on Fridays."
```

❌ Personal
❌ Punishment-focused
❌ Doesn't fix system
❌ Bhai will hide next mistake

### Good Post-Mortem (Blameless)

```
"Deployment process allowed untested code through.
CI/CD pipeline lacks integration tests for X.
Code review missed Y because no checklist."

Actions:
- Add integration test
- Create code review checklist
- Block Friday deploys (auto)
```

✅ System-focused
✅ Process improvement
✅ Future incidents prevented

### Why It Works

**Humans WILL make mistakes.** Systems should make mistakes hard.

```
Good system: Hard to make mistake
Bad system: Easy to make mistake (and blames human)
```

---

## Part 5: Post-Mortem Structure

### Standard Template

```
# Post-Mortem: [Brief Description]

**Date**: 2026-03-15
**Severity**: SEV-1
**Duration**: 47 minutes
**Authors**: [Incident Commander name]
**Status**: Draft / Review / Final

## TL;DR
[2-3 sentence summary]

## Impact
- Users affected: 100k
- Revenue impact: $50k
- Duration: 47 min
- Customer reports: 250

## Timeline
14:00 - Alert fired
14:02 - On-call acknowledged
14:05 - SEV-1 declared
...
14:47 - Resolution confirmed

## Root Cause
[Technical explanation]

## Contributing Factors
1. ...
2. ...

## What Went Well
- Quick detection
- Good communication
- Effective rollback

## What Went Poorly
- Alert was late
- Runbook was outdated
- Rollback failed first time

## Action Items
| # | Action | Owner | Due | Status |
|---|--------|-------|-----|--------|
| 1 | Add monitoring | Bhai | 2026-03-22 | Open |
| 2 | Update runbook | Priya | 2026-03-29 | Open |

## Lessons Learned
[What the team learned]
```

---

## Part 6: Writing Each Section

### TL;DR

> **2-3 sentences** for busy executives.

Example:
> "On 2026-03-15, our API returned 500 errors for 47 minutes due to database connection pool exhaustion. 100k users affected. Resolved by rolling back deploy."

### Impact

> **Quantify** the damage.

- Customers affected (count or %)
- Revenue impact ($)
- Duration (mins/hours)
- Data loss (if any)
- Customer reports
- SLA breach

### Timeline (Most Important)

> **Minute-by-minute** sequence.

```
14:00 - Deploy started
14:05 - Deploy completed
14:08 - First alert fires (DB connections high)
14:09 - On-call acknowledged
14:12 - Slack channel opened
14:15 - SEV-1 declared
14:18 - Started investigation
14:22 - Identified bad deploy
14:25 - Rollback initiated
14:30 - Rollback failed (timeout)
14:35 - Manual rollback succeeded
14:40 - Errors decreasing
14:45 - Confirmed normal
14:47 - Incident resolved
```

**Why timeline matters:**
- Identifies delays
- Highlights communication gaps
- Reveals response time

### Root Cause

> **Why** did this happen? Technical explanation.

**Use the 5 Whys** technique:

```
Q1: Why API returned 500?
A1: Database connection pool exhausted.

Q2: Why was pool exhausted?
A2: New code opened connections without closing.

Q3: Why didn't code review catch this?
A3: Reviewer didn't notice missing close.

Q4: Why didn't tests catch this?
A4: No tests for connection leak.

Q5: Why no such tests?
A5: Connection lifecycle never tested.

Root Cause: Lack of connection lifecycle testing
```

### Contributing Factors

> **What else made it worse?**

Not root cause, but exacerbating:

- Deploy was Friday afternoon
- Senior on vacation
- Documentation outdated
- Monitoring lag

### What Went Well

> **Recognize good response.** Builds confidence.

- "Alert fired within 1 minute"
- "Team responded in 3 minutes"
- "Rollback completed quickly"
- "Customer comms timely"

### What Went Poorly

> **Areas to improve.** Honest.

- "Alert noise made it easy to dismiss"
- "Runbook missing step for X"
- "Took 5 minutes to find dashboard"
- "Customer support not in incident channel"

### Action Items

> **Concrete next steps.** Owned, dated.

#### Good Action Items

```
✅ "Add automated tests for connection pool lifecycle
    Owner: Bhai
    Due: 2026-03-22
    Status: Open"
```

#### Bad Action Items

```
❌ "Be more careful with deploys"
❌ "Improve monitoring"
❌ "Better testing"
```

(Too vague, no owner, no date)

#### Categories of Action Items

1. **Prevent**: Stop this exact issue
2. **Detect**: Find faster next time
3. **Respond**: Faster mitigation
4. **Document**: Better runbook

---

## Part 7: Tone & Language

### Use Passive Voice for Failures

❌ "Bhai forgot to add tests"
✅ "Tests were missing"

❌ "Priya didn't update runbook"
✅ "Runbook update wasn't completed"

**Removes accusation.**

### Use Active Voice for Wins

✅ "Bhai quickly identified the issue"
✅ "Priya led the rollback efficiently"

**Credit when due.**

### Avoid

❌ "Should have"
❌ "Could have"
❌ "Why didn't you..."

### Use

✅ "Going forward"
✅ "Improvement opportunity"
✅ "System constraint"

---

## Part 8: Common Mistakes in Post-Mortems

### Mistake 1: Blame Hidden in System Language

> "The system that Bhai deployed without testing..."

Still blaming. Be careful.

### Mistake 2: Surface-Level Root Cause

> "Root cause: bad code."

Not root cause. **Why** bad code? **Why** it shipped?

### Mistake 3: Action Items Without Owners

> "Improve testing." (Who? When? How measured?)

### Mistake 4: Never Following Up

Action items written, never done.
**Track action items separately. Review monthly.**

### Mistake 5: Too Long

50-page post-mortem = nobody reads.
**5-10 pages max. Focus, not everything.**

### Mistake 6: Too Short

"Site went down, we fixed it" — useless.

### Mistake 7: Late Publication

Published 3 months later = forgotten.
**Publish within 1 week.**

---

## Part 9: Post-Mortem Meeting

### Format

```
Time: 30-60 minutes
Attendees: Incident responders + interested parties
Facilitator: Incident commander or manager
```

### Agenda

```
1. Read TL;DR (5 min)
2. Walk through timeline (10 min)
3. Discuss root cause (10 min)
4. Brainstorm action items (15 min)
5. Assign owners (5 min)
```

### Rules

- **Blameless**: System focus
- **Honest**: Don't sugar-coat
- **Curious**: Ask "why"
- **Constructive**: Solutions over criticism
- **Time-boxed**: 1 hour max

### Roles

- **Facilitator**: Keeps discussion on track
- **Note-taker**: Captures action items
- **Subject matter experts**: Explain technical
- **Manager**: Removes blockers

---

## Part 10: Sharing the Post-Mortem

### Internal Audience

- **Engineering team**: Full doc, all details
- **Leadership**: TL;DR + action items
- **Other teams**: Lessons learned
- **Customer success**: Customer-facing summary

### External Audience (When Public)

#### Status Page Update

```
Final update:
"We experienced an outage on March 15 affecting our API.
Root cause was a database connection issue from a deploy.
Resolved by rollback. We're implementing additional
monitoring and tests to prevent recurrence.
We apologize for the inconvenience."
```

#### Public Post-Mortem (Optional)

Some companies (Cloudflare, GitHub) publish public post-mortems. Builds trust.

---

## Part 11: Post-Mortem Categories

### Type 1: Service Outage

Standard format. Most common.

### Type 2: Security Breach

Additional sections:
- What data was exposed?
- How was it accessed?
- Notification timeline
- Legal/compliance steps

### Type 3: Data Loss

- What data was lost?
- Can it be recovered?
- Customer impact
- Restoration plan

### Type 4: Performance Degradation

- Affected metric (latency, throughput)
- Root cause analysis
- Capacity planning improvements

### Type 5: Near Miss

> Almost an incident, but avoided.

**Still write a post-mortem!** Catches issues before they explode.

---

## Part 12: Action Item Tracking

### Where to Track

- **Jira**: Create as tickets
- **GitHub**: Issues with label
- **Linear**: Action items list
- **Spreadsheet**: Simple option

### Categories

```
Severity 1 (urgent):
- Fixes that prevent same incident
- Due in 1-2 weeks

Severity 2 (important):
- Long-term improvements
- Due in 1-3 months

Severity 3 (nice-to-have):
- Process improvements
- Due in 6 months
```

### Monthly Review

> **Every month**, review open action items.

- What's done?
- What's stuck? Why?
- What's overdue?
- New incidents creating more items?

---

## Part 13: Famous Post-Mortem Examples

### Notable Public Post-Mortems (Read These!)

1. **GitLab Database Deletion (2017)**: Junior accidentally deleted prod DB. **Transparent, blameless, educational.**

2. **Cloudflare Outage (2019)**: Regex bug caused global outage. **Detailed technical explanation.**

3. **AWS S3 Outage (2017)**: Engineer typo in command. **System-level fixes.**

4. **Stripe Outage (2019)**: Database upgrade gone wrong. **Honest about communication failures.**

### What Makes Them Great

- Honest
- Blameless
- Technical depth
- Clear action items
- Published publicly

---

## Part 14: Bhai's Post-Mortem Template

```
# Post-Mortem: [TITLE]

**Date**: YYYY-MM-DD
**Severity**: SEV-X
**Duration**: X minutes/hours
**Status**: [Resolved/Ongoing]
**Authors**: [Names]
**Reviewers**: [Names]

---

## TL;DR
[2-3 sentence summary for executives]

---

## Impact

### Customers
- Affected: [number/percentage]
- Geography: [regions]
- Customer reports: [count]

### Business
- Revenue: [$amount]
- SLA: [breached? credits?]
- Reputation: [press? social?]

### Technical
- Services affected: [list]
- Data: [any loss?]

---

## Timeline (All times in IST)

| Time | Event |
|------|-------|
| 14:00 | Deploy initiated |
| 14:05 | Deploy complete |
| 14:08 | First alert fires |
| 14:09 | On-call acknowledged |
| 14:12 | Incident channel opened |
| 14:15 | SEV-1 declared |
| 14:18 | Investigation began |
| 14:22 | Root cause identified |
| 14:25 | Rollback initiated |
| 14:35 | Rollback complete |
| 14:45 | Service recovered |
| 14:47 | Incident closed |

---

## Root Cause

[Detailed technical explanation]

### 5 Whys Analysis

Q1: [question]
A1: [answer]

Q2: [question]
A2: [answer]

[Continue until root cause]

**Root Cause**: [Final answer]

---

## Contributing Factors

1. **Factor 1**: [Description]
2. **Factor 2**: [Description]
3. **Factor 3**: [Description]

---

## Detection

- **How detected**: [Alert/Customer report/Manual]
- **Time to detection**: [X minutes from incident start]
- **What could've detected faster**: [Analysis]

---

## Response

- **Time to mitigation**: [X minutes]
- **Mitigation method**: [Rollback/Restart/etc.]
- **What worked well**: [List]
- **What was slow**: [List]

---

## What Went Well 🎉

- [Item 1]
- [Item 2]
- [Item 3]

---

## What Went Poorly 😞

- [Item 1]
- [Item 2]
- [Item 3]

---

## Lessons Learned 💡

- [Lesson 1]
- [Lesson 2]
- [Lesson 3]

---

## Action Items

### Prevent (Stop this exact issue)

| # | Action | Owner | Due | Priority | Status |
|---|--------|-------|-----|----------|--------|
| 1 | [Action] | @user | YYYY-MM-DD | P0 | Open |

### Detect (Find faster next time)

| # | Action | Owner | Due | Priority | Status |
|---|--------|-------|-----|----------|--------|

### Respond (Faster mitigation)

| # | Action | Owner | Due | Priority | Status |
|---|--------|-------|-----|----------|--------|

### Document (Better knowledge)

| # | Action | Owner | Due | Priority | Status |
|---|--------|-------|-----|----------|--------|

---

## References

- Alert: [link]
- Slack channel: #incident-xyz
- Related PRs: [links]
- Customer reports: [link]

---

## Acknowledgments

Thanks to: [team members who responded]
```

---

## Part 15: Tools

### Document Hosting

- **Confluence**: Enterprise
- **Notion**: Modern
- **Google Docs**: Simple
- **Markdown in Git**: Engineering-friendly

### Incident Management

- **incident.io**: Auto-generates post-mortem template
- **FireHydrant**: Tracks throughout
- **PagerDuty**: Integrates

### Action Item Tracking

- **Jira**: Tickets
- **Linear**: Modern
- **GitHub Issues**: Free

---

## Part 16: When to Skip Post-Mortem

> **Rarely skip!** But sometimes okay:

- Very minor (SEV-4)
- Already documented (similar incident)
- Single-person impact

**When in doubt, write it.**

---

## Part 17: Building Post-Mortem Culture

### Steps

1. **Start small**: Pick worst incident, do it
2. **Make it public**: Share org-wide
3. **No punishment**: Even if mistake clear
4. **Track follow-through**: Action items closed
5. **Celebrate learnings**: "We caught X because of post-mortem!"
6. **Repeat**: Every SEV-1 and SEV-2

### Anti-Patterns to Avoid

❌ "We don't have time"
❌ "It's just one issue"
❌ "We know what happened"
❌ "Let's move on"

These erode quality over time.

---

## Part 18: Q&A

### Q: Who should write the post-mortem?
**A**: Incident commander, with help from responders.

### Q: When to publish?
**A**: Within 1 week. Sooner if SEV-1.

### Q: What if root cause is human error?
**A**: Then system failed to prevent human error. Fix system.

### Q: Should we share publicly?
**A**: Depends on company. Public builds trust but exposes internals.

### Q: How long should it be?
**A**: 5-15 pages typical. Long enough to learn, short enough to read.

### Q: What if action items never close?
**A**: Escalate. Stuck = leadership decision needed.

### Q: First post-mortem ever?
**A**: Start with template, get senior to review. Iterate.

---

## 🎯 Bhai's Final Words

> **Post-mortem is gift to future you. Today's pain → tomorrow's wisdom. Blameless, honest, actionable.**

3 Mantras:
1. **Systems fail, not people**
2. **Document for next time**
3. **Track action items to closure**

After 10 post-mortems, you'll prevent 10x more incidents than 10 random fixes. 🚀
