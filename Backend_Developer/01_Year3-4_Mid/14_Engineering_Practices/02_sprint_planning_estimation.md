# 📅 Sprint Planning & Estimation — Architecture Guide

> **Target:** 3-4 YOE | **Goal:** Agile, Scrum, sprint planning, story points — process aur mindset samjhna.

---

## Part 1: WHAT — Sprint Planning Kya Hai?

### Definition

> **Sprint** = fixed time period (usually 2 weeks) jisme team ek **set of tasks** complete karti hai. **Sprint Planning** = us 2 weeks ka plan banana.

### Real-Life Analogy 🍽️

Soch tu **shaadi ka khana banwa raha hai**:
- Total guests: 500
- Total dishes: 20 varieties
- Time: 6 ghante

**Sprint planning** = "agle 2 hours me kya banayenge, kitne log kaam karenge, kitna ready hoga" decide karna.

---

## Part 2: WHY — Sprint Planning Kyu Zaroori?

### Reason 1: Predictability

Stakeholders ko pata hona chahiye **kab kya release hoga**. Without planning = chaos.

### Reason 2: Team Alignment

10 developers, har koi kuch alag bana raha hai = waste. Planning = single direction.

### Reason 3: Realistic Commitments

"15 features in 2 weeks" without planning = burnout, missed deadlines, broken code.

### Reason 4: Risk Management

Planning me **risks identify** hote hai pehle se. Mid-sprint surprises kam.

### Reason 5: Continuous Improvement

Sprint end pe retro — kya seekha, kya improve karna.

---

## Part 3: HOW — Agile + Scrum Architecture

### The Framework

```
┌──────────────────────────────────────┐
│  PRODUCT BACKLOG                     │
│  (All future work, prioritized)      │
│                                       │
│  [P0] User auth                      │
│  [P0] Payment integration            │
│  [P1] Email notifications            │
│  [P1] Admin dashboard                │
│  [P2] Reporting                      │
│  [P2] Multi-language                 │
└────────────┬─────────────────────────┘
             │
             │ Sprint Planning
             ▼
┌──────────────────────────────────────┐
│  SPRINT BACKLOG (2 weeks)            │
│                                       │
│  Stories selected for THIS sprint    │
│  - User auth (story 1)               │
│  - Payment integration (story 2)     │
│  - Email setup (story 3)             │
└────────────┬─────────────────────────┘
             │
             │ Daily Standups
             ▼
┌──────────────────────────────────────┐
│  SPRINT EXECUTION                    │
│  - Code, test, review                │
│  - Deploy to staging                 │
│  - User testing                      │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│  SPRINT REVIEW + RETROSPECTIVE       │
│  - Demo to stakeholders              │
│  - What went well                    │
│  - What can improve                  │
└──────────────────────────────────────┘
```

---

## Part 4: Scrum Roles

### Product Owner (PO)

> **Decides WHAT to build.** Prioritizes backlog, talks to customers.

### Scrum Master

> **Facilitates the process.** Removes blockers, runs meetings, protects team.

### Development Team (You)

> **Decides HOW to build.** Engineers, designers, QA.

### Stakeholders

> **Business folks who want the product.** Get updates, not in daily work.

---

## Part 5: Scrum Ceremonies (Meetings)

### 1. Sprint Planning (Start of Sprint)

**Duration**: 1-4 hours (depends on sprint length)

**Who**: Whole team

**Output**:
- Sprint goal
- Sprint backlog (committed stories)
- Task breakdown

### 2. Daily Standup

**Duration**: 15 minutes (max!)

**Who**: Development team

**3 Questions**:
1. What did I do yesterday?
2. What will I do today?
3. Any blockers?

**NOT** for problem-solving — that's separate.

### 3. Sprint Review (End of Sprint)

**Duration**: 1-2 hours

**Who**: Team + Stakeholders

**Activity**: Demo what was built. Get feedback.

### 4. Sprint Retrospective (End of Sprint)

**Duration**: 1 hour

**Who**: Team only (no stakeholders)

**Topics**:
- What went well?
- What could improve?
- Action items for next sprint?

### 5. Backlog Refinement (Anytime)

**Duration**: 1-2 hours weekly

**Activity**: Groom upcoming stories. Add details, split, estimate.

---

## Part 6: User Stories — The Currency

### Format

```
As a [user type]
I want [feature]
So that [benefit]
```

### Example

```
As a customer
I want to reset my password via email
So that I can regain access if I forget it
```

### Acceptance Criteria

What "done" looks like:

```
- User can click "Forgot Password" on login screen
- User receives reset email within 1 minute
- Reset link expires in 24 hours
- New password must be 8+ chars
- After reset, user redirected to login
```

### Definition of Done (DoD)

Team-agreed criteria for all stories:
- Code written
- Tests passing (unit + integration)
- Code reviewed
- Deployed to staging
- PO approved
- Documentation updated

---

## Part 7: Estimation — The Hard Part

### Why Estimate?

> **To plan capacity.** Without estimates, can't commit to sprint.

### Why Estimation is Hard

1. Software is unique (not factory production)
2. Unknown unknowns
3. Dependencies on others
4. Cognitive bias (always optimistic)

### Estimation Methods

#### Method 1: Hours

```
Story X = 8 hours
Story Y = 16 hours
```

**Problem**: Inaccurate, varies by person.

#### Method 2: Story Points (Recommended)

```
Story X = 3 points
Story Y = 5 points
```

**Story points** measure:
- Complexity
- Risk
- Effort (relative)
- NOT just time

### The Fibonacci Sequence

Story points usually:
```
1, 2, 3, 5, 8, 13, 21
```

**Why Fibonacci?**
- Forces decisive thinking (no 4 or 7)
- Reflects uncertainty (bigger = less precise)
- Standard in industry

### Anchor Stories

Pick a known small story = "1 point". Compare new stories to it.

```
"Login button color change" = 1 point (anchor)
"User profile page" = ? compared to that
```

### Planning Poker

Whole team estimates together:
1. Read story
2. Each person picks card (1, 2, 3, 5, 8, 13)
3. Reveal simultaneously
4. Discuss differences
5. Re-estimate
6. Reach consensus

**Why**: Avoid groupthink, get diverse perspectives.

---

## Part 8: Velocity — How Much Team Can Do

### Concept

> **Velocity = points completed per sprint.** Team's "speed."

### Example

```
Sprint 1: Completed 20 points
Sprint 2: Completed 25 points
Sprint 3: Completed 22 points
Average velocity: ~22 points

Next sprint capacity: ~22 points
```

### Use Velocity For Planning

```
Sprint 5 planning:
- Average velocity: 22 points
- Estimated stories total: 25 points
- Decision: Drop some / split / commit
```

### Velocity Anti-Patterns

❌ Comparing teams' velocities (different baselines)
❌ Demanding velocity increase (gaming the system)
❌ Treating velocity as productivity (it's a planning tool)
✅ Using velocity for **own team's planning**

---

## Part 9: Sprint Planning Process (Step-by-Step)

### Step 1: Review Sprint Goal

> **What's the ONE big thing this sprint achieves?**

Examples:
- "Ship MVP authentication"
- "Reduce checkout latency by 50%"
- "Launch new dashboard"

### Step 2: Review Capacity

```
Team size: 5 developers
Sprint days: 10 working days
Vacation: 0 days
Capacity: 5 × 10 = 50 person-days

Subtract:
- Meetings: -10%
- Reviews: -10%
- Unexpected: -10%

Net capacity: 50 × 0.7 = 35 person-days
```

### Step 3: Select Stories from Backlog

Highest priority first. Until capacity (or velocity) is filled.

### Step 4: Break Stories into Tasks

```
Story: "User can reset password"

Tasks:
- Backend API: forgot-password endpoint (4h)
- Backend API: reset-password endpoint (4h)
- Email template (2h)
- Frontend: forgot password screen (4h)
- Frontend: reset password screen (4h)
- Tests (4h)
- QA (2h)

Total: 24h
```

### Step 5: Assign Owners

```
Backend: Bhai
Frontend: Priya
QA: Rahul
```

### Step 6: Identify Risks/Dependencies

```
- Need DevOps to add SES (email service): blocking
- Need design from designer: in progress
- Need PM to confirm 24-hour expiry: needed
```

### Step 7: Commit

Team commits to sprint scope. **PO doesn't add mid-sprint.**

---

## Part 10: Story Point Calibration

### "1 Point" Examples

- Change button color
- Fix typo
- Add log statement
- Update README

### "2 Points" Examples

- Add new field to existing form
- Fix small bug (root cause known)
- Add API endpoint (existing pattern)

### "3 Points" Examples

- New small feature
- Refactor a module
- Bug fix (need investigation)

### "5 Points" Examples

- New medium feature
- New API with auth
- Database schema change

### "8 Points" Examples

- New large feature
- Major refactor
- Multi-day investigation

### "13 Points" Examples

- Likely needs splitting
- Big architectural change
- Spans 2+ sprints

### "21+ Points"

> **STOP. Split it.** Too big to estimate accurately.

---

## Part 11: Common Estimation Mistakes

### Mistake 1: Optimism Bias

> "I can do this in 1 day."
> Reality: 3 days.

**Fix**: Use historical data, not gut feeling.

### Mistake 2: Forgetting Unknowns

> Estimate: "8 hours to add feature."
> Reality: 8 hours code + 4 hours debugging + 2 hours code review + 2 hours QA = 16 hours.

**Fix**: Include all work in estimate.

### Mistake 3: Yak Shaving

> "Quick fix to bug X"
> But bug X requires fixing library Y
> Library Y has bug Z

**Fix**: Time-box research. Spike stories.

### Mistake 4: Confusing Complexity with Time

> Complex problem, but seen before = quick.
> Simple problem, never seen = takes time.

**Fix**: Story points measure complexity + uncertainty.

### Mistake 5: Estimating Alone

> One person's view = biased.

**Fix**: Planning poker.

### Mistake 6: Committing Too Much

> "We've never done 40 points, but let's try!"

**Fix**: Stick to velocity ± 10%.

---

## Part 12: Spike Stories

### When to Use

> **Uncertain estimate?** Time-box research.

```
Story: "Investigate if we can use library X"
Time-box: 4 hours
Output: Decision + estimate for actual implementation
```

After spike, can estimate the real story.

---

## Part 13: Definition of Ready (DoR)

> **Story ready to be worked on?**

Checklist:
- [ ] User story clear (As a... I want... So that...)
- [ ] Acceptance criteria defined
- [ ] Design mockups (if UI)
- [ ] Dependencies identified
- [ ] Story sized (estimated)
- [ ] No blocking questions

**Stories not "ready" don't enter sprint.**

---

## Part 14: Backlog Health

### Healthy Backlog

```
Top 5 stories: DoR ready, well-defined
Next 10 stories: roughly defined
Next 20 stories: rough ideas
Rest: vision/themes
```

**Prioritized**, **refined just-in-time**.

### Unhealthy Backlog

❌ 500 vague stories
❌ Nothing prioritized
❌ Same story years old
❌ Conflicting items

**Fix**: Regular backlog refinement sessions.

---

## Part 15: Daily Standup Best Practices

### What Standup IS

- Status sync
- Blocker surfacing
- Quick alignment

### What Standup ISN'T

- Problem-solving session
- Status report to manager
- Lecture

### Format

Each person, 60-90 seconds:
1. **Yesterday**: Completed task X
2. **Today**: Working on task Y
3. **Blockers**: Need help with Z

After standup, **side conversations** for deep dives.

### Tips

- **Standing** (literally) keeps it short
- Same time daily
- Same place (or video link)
- Don't skip!

---

## Part 16: Retrospective Patterns

### Pattern 1: Start/Stop/Continue

```
START: What should we start doing?
STOP: What should we stop doing?
CONTINUE: What's working, keep doing?
```

### Pattern 2: Mad/Sad/Glad

```
MAD: What frustrated us?
SAD: What disappointed us?
GLAD: What made us happy?
```

### Pattern 3: 4Ls

```
LIKED: What we liked?
LEARNED: What we learned?
LACKED: What was missing?
LONGED FOR: What we wanted?
```

### Output: Action Items

Always end with **3-5 concrete actions** for next sprint:

```
1. Move standup to 10 AM
2. Pair-program for tricky stories
3. Block 2 hours daily for deep work
```

Track these in next retro.

---

## Part 17: Agile vs Waterfall

### Waterfall

```
Requirements → Design → Code → Test → Deploy
(linear, each phase complete before next)
```

**Problem**: 6 months later, requirements changed.

### Agile

```
Sprint 1: Small piece → working software
Sprint 2: Add piece → working software
...
(iterative, adaptable)
```

**Why agile won**: Software change fast. Customers change minds. Waterfall too rigid.

---

## Part 18: Variations

### Scrum

> Sprints (2-3 weeks), all ceremonies. **Most common.**

### Kanban

> Continuous flow, no sprints. WIP limits.

```
TODO  | IN PROGRESS (3 max) | REVIEW | DONE
```

**Good for**: Support teams, ops.

### Scrumban

> Mix of Scrum + Kanban.

### XP (Extreme Programming)

> Heavy on engineering practices: TDD, pair programming, refactoring.

---

## Part 19: Tools

### Jira (Industry Standard)
- Backlog management
- Sprint tracking
- Reporting
- Heavy but powerful

### Linear (Modern)
- Fast, clean UI
- Engineering-focused
- Popular at startups

### GitHub Projects
- Built into GitHub
- Free with org
- Basic but improving

### Notion / Asana / Trello
- Less engineering-specific
- Good for small teams

---

## Part 20: Working with Estimates as Promises

### Reality Check

Estimates **are not promises**.
- Plan with them
- Track velocity
- Communicate if missing

### When Behind

> Don't silently miss deadline. Communicate ASAP.

Options:
- Descope (drop features)
- Extend deadline
- Add resources (usually doesn't work)

### After Sprint

Honest retrospective:
- Why missed?
- What learned?
- How to estimate better?

---

## Part 21: Q&A

### Q: 2 weeks vs 1 week vs 4 week sprints?
**A**: 2 weeks most common. 1 week = too much overhead. 4 weeks = too long for course-correction.

### Q: Story points vs hours?
**A**: Story points for planning. Hours for very short tasks (sub-day).

### Q: Can scope change mid-sprint?
**A**: Generally no. If critical, swap (remove equivalent points). PO doesn't add for free.

### Q: What if I finish my tasks early?
**A**: Help teammates, pick next priority, technical debt, learning.

### Q: Junior wants to commit too much?
**A**: Mentor on realistic estimation. Use velocity data.

### Q: Boss demands faster velocity?
**A**: Educate that velocity is planning tool, not productivity metric. Forcing it = gaming, bad code, burnout.

### Q: What about non-coding work?
**A**: Estimate too. Meetings, support, learning all count toward capacity.

---

## 🎯 Bhai's Final Words

> **Agile is mindset, not ceremony. Sprint planning ka goal — predictable delivery, not perfect prediction. Estimates galat hote rahenge, but trend over time reveals truth.**

3 Mantras:
1. **Estimate as team**, not solo
2. **Track velocity** over individual hours
3. **Continuous improvement** via retros

Mid-level dev jab estimation accurate karne lagta hai = senior bana. Practice karta ja. 🚀
