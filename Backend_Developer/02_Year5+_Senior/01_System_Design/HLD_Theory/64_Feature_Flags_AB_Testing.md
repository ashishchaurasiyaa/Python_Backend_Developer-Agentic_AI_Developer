# Feature Flags & A/B Testing Design

---

## Feature Flags (Feature Toggles)

### What is it?
A mechanism to enable/disable features at runtime without deploying new code.

```python
# Without feature flag — deploy to enable
def checkout():
    return new_checkout_flow()

# With feature flag — toggle without deploy
def checkout(user_id):
    if feature_flag.is_enabled("new_checkout", user_id):
        return new_checkout_flow()
    return old_checkout_flow()
```

---

### Types of Feature Flags

| Type | Purpose | Example |
|------|---------|---------|
| Release flag | Hide incomplete feature in prod | New payment UI not ready |
| Experiment flag | A/B testing | 50% users see new homepage |
| Ops flag | Kill switch for problematic feature | Disable heavy report if DB is slow |
| Permission flag | Feature for specific users | Beta users only |

---

### System Design — Feature Flag Service

```
┌─────────────────────────────────────────────┐
│              Feature Flag Service            │
│                                             │
│  ┌──────────┐   ┌──────────┐  ┌──────────┐ │
│  │  Flag DB │   │ Rule     │  │  Audit   │ │
│  │(Postgres)│   │ Engine   │  │  Log     │ │
│  └──────────┘   └──────────┘  └──────────┘ │
└─────────────────────────────────────────────┘
          │
          │ evaluated flag (true/false)
          ▼
     Application (cached locally)
```

**Flag evaluation rules:**
- User ID % 100 < 50 → enabled (50% rollout)
- User is in beta_users group → enabled
- User's country == "IN" → enabled
- Always enabled for internal employees

### Key Design Decisions

**1. Caching flags locally**
Don't call the flag service on every request — too slow.
```
App starts → fetch all flags → cache in memory (TTL: 30 seconds)
Background thread refreshes cache every 30s
```

**2. Gradual rollout (canary release)**
```
Day 1: 1% users  → watch error rates
Day 2: 10% users → watch metrics
Day 3: 50% users
Day 4: 100% users → flag removed, code cleaned up
```

**3. Sticky bucketing**
User must always see the same variant. Use consistent hashing on user_id.
```
bucket = hash(user_id + flag_name) % 100
if bucket < rollout_percentage: enabled = True
```

---

## A/B Testing

### What is it?
Show variant A to group 1, variant B to group 2. Measure which performs better.

```
Users
  │
  ├── 50% ──► Variant A (old checkout button: "Buy Now")
  └── 50% ──► Variant B (new checkout button: "Order Now")

Measure: conversion rate, click rate, revenue per user
Winner: whichever has statistically significant better metric
```

---

### A/B Testing System Design

```
                    ┌──────────────────┐
User Request ──────►│  Assignment Svc  │──► assigns user to A or B (consistent)
                    └──────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         Feature Flag    Experiment DB   Analytics
         Service         (user→variant)  Pipeline
```

**Components:**
1. **Assignment Service** — determines which variant user sees (consistent across sessions)
2. **Experiment Config** — stores experiment definition, start/end date, traffic split
3. **Event Tracking** — logs user actions with variant info
4. **Analysis Service** — runs statistical significance tests (t-test, chi-square)

### Statistical Significance
Don't call a winner too early. Need enough data.
- Minimum sample size per variant (calculated before experiment)
- p-value < 0.05 = statistically significant (95% confidence)
- Run for at least 1-2 weeks to capture weekly patterns

---

### Experiment Isolation (Interaction Problem)
If user is in Experiment 1 (new button) AND Experiment 2 (new color), results contaminate each other.

**Solutions:**
- Layer experiments (orthogonal layers) — each layer handles different surface area
- Mutex groups — if in experiment A, cannot be in experiment B

---

## Tools Used in Industry

| Tool | Purpose |
|------|---------|
| LaunchDarkly | Feature flags as a service |
| Split.io | Feature flags + A/B testing |
| Optimizely | A/B testing platform |
| Unleash | Open source feature flags |
| Growthbook | Open source A/B testing |
| In-house (Uber, Netflix) | Custom built for scale |

---

## Real World
- **Netflix:** Tests everything — thumbnail images, UI layout, play button position
- **Facebook:** Runs thousands of A/B tests simultaneously
- **Amazon:** "1-Click Buy" was validated by A/B test
- **Airbnb:** Uses Experimentation Platform (ERF) — their own tool

---

## Interview Tip
> "We use feature flags for all new features — start at 1% internal users, gradually roll out. For A/B testing, users are consistently bucketed using a hash of user_id + experiment_id so they always see the same variant. We run experiments for minimum 2 weeks and only call a winner at p < 0.05."
