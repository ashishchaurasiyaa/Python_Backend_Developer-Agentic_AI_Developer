# 🔍 Code Review Skills — Architecture-Level Guide

> **Target:** 3-4 YOE | **Goal:** Code review dena aur lena — process, mindset, mechanics. Senior banane wala skill.

---

## Part 1: WHAT — Code Review Kya Hai?

### Definition

> **Code Review = ek developer ka code, doosre developers padhte aur feedback dete hai before merging.** Quality + knowledge transfer + bug prevention.

### Real-Life Analogy 📝

Soch tu **essay likh raha hai** for publication. Editor pehle padhega, suggestions dega:
- "Yeh paragraph clear nahi"
- "Grammar yahaan galat"
- "Yeh evidence add kar"

Phir publish hoga. **Code review bilkul waisa hi.**

---

## Part 2: WHY — Code Review Kyu Critical?

### Reason 1: Bug Prevention

> **Code review me 60-80% bugs catch hote hai BEFORE production.** Sasta hai bug fix karna abhi vs prod me.

### Reason 2: Knowledge Spread

Ek developer ka code → 3-4 developers padhte hai → **team knowledge spread**. Bus factor reduce.

### Reason 3: Mentorship

Junior ka code review = senior se sikhna. Direct teaching moment.

### Reason 4: Quality Standard

Without reviews, code quality slowly degrades. Reviews = guardrail.

### Reason 5: Security

Security issues catch karna easy in review than in production.

### Reason 6: Team Alignment

Patterns, conventions, architecture decisions — reviews me reinforce.

---

## Part 3: HOW — Code Review Architecture

### The Process

```
DEVELOPER                       REVIEWER                    TEAM
   │                               │                          │
   ├─ Writes code                  │                          │
   ├─ Creates PR                   │                          │
   │                               │                          │
   ├──── Notifies reviewer ──────► │                          │
   │                               │                          │
   │                               ├─ Reads PR                │
   │                               ├─ Reads description       │
   │                               ├─ Pulls code locally?     │
   │                               ├─ Adds comments           │
   │                               ├─ Approves / Requests     │
   │                               │   changes                │
   │                               │                          │
   │◄──── Feedback ─────────────────┤                          │
   │                               │                          │
   ├─ Addresses comments           │                          │
   ├─ Pushes updates               │                          │
   │                               │                          │
   ├──── Re-request review ──────► │                          │
   │                               │                          │
   │                               ├─ Re-reviews              │
   │                               ├─ Approves                │
   │                               │                          │
   ├─ Merges to main               │                          │
   │                                                          │
   ├──── Deploys ────────────────────────────────────────────►│
```

---

## Part 4: Two Sides of Code Review

### Side A: As Author (Receiving Reviews)

### Side B: As Reviewer (Giving Reviews)

Both skills needed. Different mindsets.

---

## Part 5: AS AUTHOR — Best Practices

### Before Creating PR

#### Self-Review First
> **Apni PR khud padh.** Diff dekh. Galtiyaan khud nikaal.

Senior ka time mat waste kar typo aur obvious mistakes me.

#### Small PRs Win
- Big PR (1000+ lines) = nobody reviews properly
- Small PR (50-200 lines) = thorough review

**Split big features into multiple PRs.**

#### Single Responsibility
One PR = one concern. Not "fix bug + add feature + refactor."

### PR Description Matters

#### Good PR Description Structure

```
## What
Brief description of change.

## Why
Why is this change needed?

## How
High-level approach.

## Testing
How was this tested?

## Screenshots (if UI)
Before/After images.

## Related
- Closes #123
- Related to #456
```

### Naming PRs

❌ `fix bug`
✅ `Fix race condition in payment processing`

❌ `update`
✅ `Update Django to 5.0 for security patches`

### Add Comments to Help Reviewer

```
This regex is intentionally non-greedy because [reason]
```

Comments to **reviewer** make their life easier.

---

## Part 6: AS AUTHOR — Receiving Feedback

### Mindset

> **Code review = your code, not your character.** Don't take personally.

### Bhai's Golden Rules

1. **Thank reviewers** — they spent time helping you
2. **Don't argue defensively** — discuss objectively
3. **Ask for clarification** — better than assume
4. **Address every comment** — even with "Won't fix, because X"
5. **Update or reply** — don't ignore

### Responding to Comments

#### "Yes, I'll fix"
- Make change
- Reply "Done" or use thumbs up

#### "I disagree, here's why"
- Explain reasoning
- Reference docs/data
- Be respectful

#### "Out of scope"
- "Good point, but out of scope for this PR. Created #999 to track."

#### "I don't understand"
- "Could you elaborate?" or "Could you show an example?"

### When Reviewer is Wrong

It happens. Politely push back with reasoning.

```
"I think this approach is better because [data/reason]. 
Open to alternatives if you see issues."
```

If still disagreement, escalate to tech lead.

---

## Part 7: AS REVIEWER — Best Practices

### The Mindset

> **You're not gatekeeper. You're collaborator.** Goal: help merge quality code, not block.

### Review Order

```
Don't dive into code first. Read in this order:

1. PR Title — what is this?
2. PR Description — why this change?
3. Tests — what's expected behavior?
4. Code changes — implementation
```

### What to Look For

#### Layer 1: Correctness (Critical)
- Does it solve the problem?
- Bugs?
- Edge cases?
- Race conditions?

#### Layer 2: Architecture (Important)
- Right abstraction?
- Follows existing patterns?
- Side effects?
- Future-proof?

#### Layer 3: Maintainability
- Readable?
- Names clear?
- Comments where needed?
- Tests present?

#### Layer 4: Performance
- Efficient queries?
- Avoidable loops?
- Memory usage?

#### Layer 5: Security
- Auth checks?
- Input validation?
- Secrets in code?
- SQL injection risk?

#### Layer 6: Style (Lowest priority)
- Linter should catch
- Don't waste time on these

---

## Part 8: Comment Categories (Use Prefixes)

### Severity Prefixes

```
[blocker]    Must fix before merge
[concern]    Worth discussing
[suggestion] Nice to have
[nit]        Trivial style preference
[question]   Clarification needed
[praise]     Good code, recognized!
```

### Examples

```
[blocker] This will cause SQL injection. Use parameterized query.

[concern] This loop is O(n²). With 10k items, will be slow. Worth optimizing?

[suggestion] Could extract this into a helper function for reuse.

[nit] Trailing whitespace.

[question] Why did you choose List over Set here?

[praise] Nice use of context manager here, much cleaner than try/finally.
```

---

## Part 9: Giving Constructive Feedback

### Bad Feedback ❌

```
"This code is bad."
"Why did you write it like this?"
"You should know better."
```

### Good Feedback ✅

```
"Consider using X here because [specific reason]."

"This works, but I think Y might be clearer because [reason]."

"In our codebase we usually use pattern Z. Mind switching for consistency?"
```

### Be Specific

❌ "Refactor this"
✅ "Extract lines 45-60 into a helper function `validate_user_input()`"

### Suggest Alternatives

Don't just criticize. **Propose solutions.**

### Frame as Questions

Instead of "This is wrong", say "Could this break if X?"

### Pull Request, Not Push

> Give suggestions, not commands. Author owns the code.

---

## Part 10: Time Allocation

### Quick Reviews (< 50 lines)
- 15-30 minutes
- Same-day turnaround expected

### Medium Reviews (50-300 lines)
- 30-60 minutes
- 24-hour turnaround

### Large Reviews (300+ lines)
- 1-2 hours
- 48-hour turnaround
- **Ideally split into smaller PRs**

### Bhai's Rule

> If review takes > 2 hours, ask author to split.

---

## Part 11: Tools

### GitHub PR

Standard for most teams.
- File-by-file review
- Inline comments
- Suggestions (auto-applies if accepted)
- Required reviewers
- Status checks

### GitLab Merge Requests

Similar to GitHub.
- Approvals
- Discussions
- CI integration

### Bitbucket

Less common but works.

### Phabricator (Older)

Used at Facebook, others.

### Gerrit (Strict)

Used at Google.

### CodeStream (IDE Integration)

Reviews in VS Code.

---

## Part 12: CI/CD Integration

### Auto-Checks Before Review

Before human reviews, CI checks:
- Linter passes (ruff)
- Type checker passes (mypy)
- Tests pass
- Coverage threshold
- Security scans

**These automated checks save reviewer time.**

### Required Status Checks

Block merge if:
- Tests fail
- Coverage drops
- Lint issues
- Security vulnerabilities

---

## Part 13: Review Etiquette

### DO

✅ Be timely (within 24h)
✅ Be specific
✅ Be respectful
✅ Acknowledge effort
✅ Suggest alternatives
✅ Use praise
✅ Ask before refactoring suggestion

### DON'T

❌ Be dismissive
❌ Make it personal
❌ Block on trivial nits
❌ Bikeshed (debate minor things)
❌ Use sarcasm
❌ "I would have done X" (unhelpful)
❌ Ghost the PR (no response)

---

## Part 14: Different Review Styles

### Style 1: Pre-Approval Review

- Reviewer must explicitly approve
- LGTM (Looks Good To Me)
- Standard at most companies

### Style 2: Post-Commit Review

- Code merged immediately
- Reviewed afterward
- Trust-based (small teams)

### Style 3: Pair Programming as Review

- 2 devs code together
- Real-time review
- No async review needed

### Style 4: Trunk-Based with Toggles

- Code in main always
- Feature flags control rollout
- Less review pressure

---

## Part 15: Specific Things to Check

### Data Changes
- Migrations safe?
- Backward compatible?
- Downtime needed?

### Performance
- N+1 queries?
- Database indexes?
- Caching needed?

### Security
- Auth/authz checks?
- Input validation?
- Sensitive data logged?
- HTTPS only?

### Logging
- Useful log messages?
- Sensitive data not logged?
- Log level correct?

### Error Handling
- Errors caught?
- Errors logged?
- User sees friendly message?
- No silent failures?

### Tests
- Unit tests for new logic?
- Integration tests for flows?
- Edge cases covered?

---

## Part 16: Architecture Reviews (Advanced)

### When to Do

Big changes:
- New service
- Architecture shift
- Major refactor

### What to Check

1. **Design Doc Read** — read ADR first
2. **Service Boundaries** — clear?
3. **Data Flow** — sound?
4. **Failure Modes** — what if X fails?
5. **Scalability** — handles 10x load?
6. **Maintainability** — long-term?

---

## Part 17: Code Review Anti-Patterns

### Anti-Pattern 1: The Rubber Stamp
"LGTM" without reading. Useless.

### Anti-Pattern 2: The Nitpicker
Endless trivial comments. Frustrating.

### Anti-Pattern 3: The Architect
"Should rewrite as microservice" on a 50-line PR. Out of scope.

### Anti-Pattern 4: The Ghoster
Asked to review, never responds.

### Anti-Pattern 5: The Bottleneck
One person reviews everything. Single point of failure.

### Anti-Pattern 6: The Battlefield
Review becomes argument. Toxic.

### Anti-Pattern 7: The Gatekeeper
Blocks for personal preference.

---

## Part 18: Metrics That Matter

### Healthy Review Metrics

| Metric | Target |
|--------|--------|
| Time to first review | < 24h |
| Time to merge | < 3 days |
| PR size | < 300 lines |
| Reviewers per PR | 1-3 |
| Comments per PR | 5-15 (sweet spot) |

### Unhealthy Signs

- PRs sit for weeks
- Massive PRs (1000+ lines)
- Same person always reviews
- No comments on big PRs (rubber stamp)
- 50+ comments (poor quality code)

---

## Part 19: Difficult Situations

### Reviewing Senior's Code

Tu junior, senior ka code review karna hai. Awkward.

**Approach:**
- Be respectful but honest
- Ask questions: "Why this approach?"
- Use [suggestion] not [blocker]
- Senior values fresh eyes

### Junior Wrote Bad Code

**Wrong**: Reject entire PR with "all wrong."
**Right**: Help understand. Be patient. Pair if needed.

### Strong Disagreement

**When you disagree:**
1. State your view clearly
2. Provide reasoning
3. Suggest alternative
4. If still disagreement, escalate to tech lead
5. Disagree and commit (sometimes)

### Time Pressure

"Need to merge NOW for release."

**Approach:**
- Quick review focused on critical only
- Note "deferred items" for later
- Don't compromise security/correctness

---

## Part 20: Bhai's Personal Code Review Checklist

```
□ Read PR title + description
□ Understand the "why"
□ Check tests exist
□ Run code locally (if complex)
□ Check for:
  □ Bugs/correctness
  □ Edge cases
  □ Security issues
  □ Performance issues
  □ Architecture fit
  □ Test coverage
  □ Documentation
□ Comments:
  □ Use prefixes [blocker/suggestion/nit]
  □ Be specific
  □ Suggest alternatives
  □ Use praise
□ Approve / Request changes
□ Follow up on author's responses
```

---

## Part 21: Q&A

### Q: Should I review every PR thoroughly?
**A**: No. Match depth to criticality. Hotfix? Quick review. Architecture change? Deep dive.

### Q: How many reviewers per PR?
**A**: 1 for small, 2 for medium, 3+ for big/risky. Depends on team size.

### Q: Should AI review code?
**A**: Tools like Copilot help. But human judgment still needed for architecture, business logic, team conventions.

### Q: What if reviewer doesn't respond?
**A**: Ping after 24h. After 48h, ask different reviewer or tech lead.

### Q: Can I review my own PR?
**A**: Most teams: No. Conflict of interest. Always need external eyes.

### Q: Should code review affect promotion?
**A**: Yes — being a great reviewer = great signal for promotion.

---

## 🎯 Bhai's Final Words

> **Code review is the most underrated skill in engineering. Junior thinks coding fast = senior. Wrong. Senior reviews code wisely, mentors juniors, prevents disasters.**

3 Mantras:
1. **Author**: Make reviewer's life easy (small PRs, good descriptions)
2. **Reviewer**: Be kind, specific, helpful
3. **Both**: Goal is quality code, not winning argument

Practice both sides daily — within 6 months, you'll be the reviewer everyone wants. 🚀
