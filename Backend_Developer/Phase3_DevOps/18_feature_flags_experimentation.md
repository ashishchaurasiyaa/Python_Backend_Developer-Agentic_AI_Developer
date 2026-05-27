# DevOps — Feature Flags & Experimentation Platforms
**Phase 3 DevOps | Senior Backend + Agentic AI**

## Quick Concepts

- **Feature flag** = runtime toggle to enable/disable code paths without redeploying
- **Release flag** = ship dark code, enable later (gradual rollout)
- **Experiment flag** = A/B test (50% see version A, 50% see B)
- **Permission flag** = user/tenant-specific feature access
- **Ops flag** = circuit breaker / kill switch
- **Targeting rule** = "enable for users where country = IN AND plan = pro"
- **Variant** = a specific value (boolean, multi-value, JSON)
- **Bucketing** = stable hash of user_id → variant (so same user sees same thing)
- **OpenFeature** = open standard for feature flag APIs (CNCF)

---

## Why Feature Flags Are 2026-Essential

```
What they unlock:
─────────────────────────────────
✓ Decouple DEPLOY from RELEASE
   Code deployed Monday, feature enabled Friday after testing

✓ Continuous deployment safety
   Risky change behind a flag, kill-switch on failure

✓ A/B testing
   Measure impact before full rollout

✓ Gradual rollouts (canary)
   1% → 10% → 50% → 100% with metrics gating each step

✓ Permission / tier features
   Premium users see X, free users don't

✓ Kill switches for incidents
   Disable buggy feature in 1 minute, not 1 hour (no redeploy)

✓ Faster experimentation = faster product learning
```

**Senior interview Q:** "How do you roll out a major change without a blast radius?"
→ Feature flags + canary + observability + auto-rollback.

---

## The Five Flag Types

| Type | Lifespan | Example | Cleanup Urgency |
|---|---|---|---|
| **Release** | Days-weeks | "new_checkout_v2" | HIGH (remove after 100%) |
| **Experiment** | Weeks | "ab_homepage_layout" | HIGH (remove after analysis) |
| **Permission** | Permanent | "tier_pro_only" | LOW (lives forever) |
| **Ops / kill** | Permanent | "disable_recommendations" | LOW (incident insurance) |
| **Custom** | Variable | tenant-specific config | varies |

**Hygiene rule:** every flag has a TTL or owner. Stale flags = bugs waiting to happen.

---

## Players in the Market (2026)

| Tool | Type | Strengths | When to Pick |
|---|---|---|---|
| **LaunchDarkly** | SaaS, paid | Industry standard, mature, expensive | Mature org, no budget pain |
| **Unleash** | Open source + SaaS | Self-host option, OSS, OpenFeature SDK | Self-host preferred, EU/India |
| **GrowthBook** | OSS + cloud | A/B testing first-class, free OSS | Experimentation focus, startup |
| **Flagsmith** | OSS + cloud | Self-host, simple model | Small team, want OSS |
| **Split.io** | SaaS | Strong analytics + experiments | Data-driven team |
| **OpenFeature** | Standard | Vendor-agnostic SDK | Want to avoid lock-in |
| **PostHog Feature Flags** | OSS + cloud | Bundled with product analytics | Already using PostHog |
| **ConfigCat** | SaaS | Cheap, simple | Tight budget, simple needs |
| **Homegrown** | DIY | Free, total control | Very specific needs |

---

## Decision Tree

```
                        ┌──────────────────────┐
                        │ Team size + budget?  │
                        └──────────┬───────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
        Startup (small)     Mid-size              Enterprise
              │                    │                    │
              ▼                    ▼                    ▼
   ┌────────────────┐   ┌──────────────────┐   ┌──────────────────┐
   │ Want OSS?      │   │ Need experiments?│   │ Compliance heavy?│
   └───┬────────────┘   └───┬──────────────┘   └───┬──────────────┘
       │                    │                       │
    Yes│ No              Yes│ No                 Yes│ No
       │  │                 │  │                   │  │
       ▼  ▼                 ▼  ▼                   ▼  ▼
   ┌────┐ ┌─────────┐  ┌────────┐ ┌──────────┐  ┌──────┐ ┌────────────┐
   │Gro │ │PostHog /│  │GrowthB │ │Unleash / │  │Unleash│ │LaunchDarkly│
   │wth │ │ConfigCat│  │Split   │ │Flagsmith │  │self-h │ │managed     │
   │Book│ │         │  │        │ │          │  │       │ │            │
   └────┘ └─────────┘  └────────┘ └──────────┘  └──────┘ └────────────┘
```

---

## Architecture — How Flags Actually Work

### Pattern: SDK + Streaming Updates

```
   Your App                  Flag Service
   ───────                   ────────────
   ┌────────┐                ┌──────────┐
   │ SDK    │◄───────────────│ Server   │
   │ Cache  │  streaming     │ + Admin  │
   │        │   updates      │   UI     │
   └────────┘                └──────────┘
       │                          ▲
       │ evaluate                  │
       │ locally (us)              │ events
       ▼                          │ (analytics)
   ┌────────┐                     │
   │ feature│                     │
   │ check  │─────────────────────┘
   └────────┘
```

Key properties:

```
✓ Local evaluation — no network call per flag check
✓ Streaming updates — flag changes propagate < 1s
✓ Fallback values — if SDK can't reach server, use default
✓ Events — SDK sends evaluation telemetry back
```

---

## OpenFeature — The Vendor-Neutral Standard

### Why It Matters

```
✗ Lock-in to LaunchDarkly's API = painful migration later
✓ OpenFeature = standard interface, swap providers freely

if-statement: openfeature.client.get_boolean("new_checkout", default=False)
```

### Install + Use (Python)

```bash
pip install openfeature-sdk
pip install openfeature-provider-unleash  # or launchdarkly, growthbook, etc.
```

```python
from openfeature import api
from openfeature.evaluation_context import EvaluationContext
# pick provider
from openfeature_provider_unleash import UnleashProvider

api.set_provider(UnleashProvider(
    url="https://unleash.example.com/api",
    api_token="...",
    app_name="my-fastapi-app",
))

client = api.get_client()

# evaluate
def checkout_view(user):
    ctx = EvaluationContext(
        targeting_key=user.id,
        attributes={"country": user.country, "plan": user.plan},
    )
    if client.get_boolean_value("new_checkout_v2", False, ctx):
        return new_checkout()
    return old_checkout()
```

---

## FastAPI Integration

### Setup as Dependency

```python
# deps.py
from fastapi import Depends, Request
from openfeature import api
from openfeature.evaluation_context import EvaluationContext


def get_flag_context(request: Request, user=Depends(get_current_user)) -> EvaluationContext:
    return EvaluationContext(
        targeting_key=user.id if user else request.client.host,
        attributes={
            "country": user.country if user else "unknown",
            "plan": user.plan if user else "anonymous",
            "tenant_id": user.tenant_id if user else None,
            "app_version": request.headers.get("X-App-Version", "unknown"),
        },
    )


def get_flag_client():
    return api.get_client()
```

### Use in Route

```python
@app.get("/checkout")
async def checkout(
    flags=Depends(get_flag_client),
    ctx=Depends(get_flag_context),
):
    if flags.get_boolean_value("new_checkout_v2", False, ctx):
        return await new_checkout_flow()

    # rollout variant
    layout = flags.get_string_value("checkout_layout", "default", ctx)
    return await checkout_with_layout(layout)


@app.get("/recommendations")
async def recommendations(flags=Depends(get_flag_client), ctx=Depends(get_flag_context)):
    # OPS flag — kill switch
    if flags.get_boolean_value("disable_recommendations", False, ctx):
        return {"recommendations": [], "reason": "temporarily_disabled"}
    return await fetch_recommendations()
```

### Type-Safe Wrapper

```python
# flags.py — centralize flag definitions
from dataclasses import dataclass
from openfeature.api import get_client


@dataclass
class Flag:
    name: str
    default: bool | str | int | dict
    description: str
    owner: str
    sunset_date: str | None = None  # YYYY-MM-DD


# Single source of truth — flag registry
NEW_CHECKOUT = Flag(
    name="new_checkout_v2",
    default=False,
    description="Roll out new checkout flow",
    owner="checkout-team",
    sunset_date="2026-07-01",
)

DISABLE_RECOMMENDATIONS = Flag(
    name="disable_recommendations",
    default=False,
    description="Kill switch for recommendations service",
    owner="search-team",
    # no sunset — permanent ops flag
)


def is_on(flag: Flag, ctx) -> bool:
    return get_client().get_boolean_value(flag.name, flag.default, ctx)


# Usage:
if is_on(NEW_CHECKOUT, ctx):
    ...
```

→ Now you have a registry. Easy to audit ALL flags.

---

## A/B Testing Pattern

### Setup

```python
# Variants: "control", "variant_a", "variant_b"
variant = flags.get_string_value("homepage_test", "control", ctx)

# Log exposure (which variant the user saw)
analytics.log_event("experiment_exposure", {
    "experiment": "homepage_test",
    "variant": variant,
    "user_id": user.id,
})

# Render variant
if variant == "variant_a":
    return render_a()
elif variant == "variant_b":
    return render_b()
else:
    return render_control()
```

### Stable Bucketing

```
Critical: same user MUST see the same variant across requests.

How: hash(user_id + experiment_name) % 100 → bucket

GrowthBook / Split do this automatically.
DON'T roll your own random() — users will see flickering UX.
```

### Analyzing Results

```sql
-- ClickHouse query for A/B test results
SELECT
    variant,
    countDistinctIf(user_id, event_type = 'view') AS users,
    countDistinctIf(user_id, event_type = 'purchase') AS purchasers,
    countDistinctIf(user_id, event_type = 'purchase') /
        countDistinctIf(user_id, event_type = 'view') AS conversion_rate,
    sumIf(amount, event_type = 'purchase') / count(*) AS avg_revenue
FROM events
WHERE experiment = 'homepage_test'
  AND event_time >= '2026-05-01'
GROUP BY variant;
```

Then run a statistical significance test (chi-square, t-test). GrowthBook does this UI-side.

---

## Gradual Rollout (Canary) Pattern

### Stages

```
Stage 1: Internal — flag enabled for employees only
   Targeting: user.email LIKE '%@yourcompany.com'

Stage 2: Beta — small % of opted-in users
   Targeting: user.beta_program = true

Stage 3: 1% rollout
   Targeting: user_id bucket % 100 < 1

Stage 4: 10% — watch error rates + p99
   Targeting: user_id bucket % 100 < 10

Stage 5: 50% — A/B compare new vs old
   Targeting: user_id bucket % 100 < 50

Stage 6: 100% — fully rolled out
   Then: schedule removal of flag

Stage 7: Cleanup — delete old code path + flag
```

### Auto-Rollback on Errors

```python
# In your circuit breaker
class FlagWithCircuitBreaker:
    def __init__(self, flag, error_threshold=0.05):
        self.flag = flag
        self.error_threshold = error_threshold

    def is_on(self, ctx):
        # Check recent error rate from observability
        if get_error_rate(self.flag.name, window="5m") > self.error_threshold:
            # AUTO-DISABLE — alert humans, fall back to default
            alert_oncall(f"Auto-disabled {self.flag.name} — error rate too high")
            return self.flag.default
        return is_on(self.flag, ctx)
```

Or use your flag service's built-in metric-based rollback (LaunchDarkly, Split support this).

---

## Self-Hosted Unleash Setup (Compact)

### Docker Compose

```yaml
# docker-compose.yml
version: "3"
services:
  unleash-db:
    image: postgres:16
    environment:
      POSTGRES_DB: unleash
      POSTGRES_USER: unleash_user
      POSTGRES_PASSWORD: secret
    volumes:
      - unleash_data:/var/lib/postgresql/data

  unleash:
    image: unleashorg/unleash-server:latest
    ports:
      - 4242:4242
    environment:
      DATABASE_URL: "postgres://unleash_user:secret@unleash-db/unleash"
      DATABASE_SSL: "false"
    depends_on:
      - unleash-db

volumes:
  unleash_data:
```

### Python Client

```bash
pip install UnleashClient
```

```python
from UnleashClient import UnleashClient

client = UnleashClient(
    url="http://localhost:4242/api/",
    app_name="my-service",
    custom_headers={"Authorization": "<your-api-token>"},
)
client.initialize_client()

if client.is_enabled("new_checkout_v2", context={"userId": user.id}):
    return new_checkout()
```

---

## Flag Lifecycle Management

### The Hygiene Problem

```
After 6 months in production:
   ✗ 47 flags exist
   ✗ 12 are 100% rolled out (should be removed)
   ✗ 8 nobody knows who owns
   ✗ 3 are dead code paths
   ✗ Engineers don't trust flags anymore

This is the silent killer of flag systems.
```

### Solutions

1. **Sunset dates** in flag metadata:
```python
sunset_date="2026-07-01"
```

2. **Dashboard for stale flags:**
```sql
-- Run weekly
SELECT name, owner, percentage_enabled, last_modified, days_at_100_percent
FROM unleash_flags
WHERE percentage_enabled = 100
  AND days_at_100_percent > 30;
-- → These should be removed
```

3. **PR template** requiring flag cleanup:
```markdown
- [ ] Flag added: name, owner, sunset date
- [ ] Flag removed: confirm no callers (grep)
```

4. **CI guard:**
```python
# Fail CI if PR adds flag without sunset_date
# Fail CI if flag exists in code but isn't in flag service
```

---

## Permission Flags Pattern

```python
# Forever flags — gates premium features
@app.post("/api/advanced-feature")
async def advanced(user=Depends(get_current_user), flags=Depends(get_flag_client)):
    ctx = EvaluationContext(
        targeting_key=user.id,
        attributes={"plan": user.plan, "tenant_id": user.tenant_id},
    )

    if not flags.get_boolean_value("feature_advanced_analytics", False, ctx):
        raise HTTPException(403, "Not available on your plan")

    return await advanced_logic()
```

In flag service, the rule is:
```
"feature_advanced_analytics" = TRUE if user.plan IN ("pro", "enterprise")
```

→ Sales can grant access via flag UI without code change.

---

## Common Patterns

### Pattern: Multi-Tenant Tier

```yaml
flag: enable_ai_features
targeting:
  - if tenant.tier == "enterprise" → ON
  - if tenant.tier == "pro" AND tenant.region != "EU" → ON
  - else → OFF
```

### Pattern: Region-Specific

```yaml
flag: new_payment_gateway
targeting:
  - if request.country == "IN" → use Razorpay
  - if request.country in ("US", "CA") → use Stripe
  - else → use PayPal
```

### Pattern: Schema Migration Behind Flag

```python
if flags.get_boolean_value("use_new_user_schema", False, ctx):
    user = User.from_v2_table(user_id)
else:
    user = User.from_v1_table(user_id)
```

Lets you migrate DB writes/reads gradually.

---

## Interview Questions & Answers

### Q1: Why is feature flagging more than just "if statements"?

**Answer:**

A naive `if SHOW_NEW_FEATURE:` requires redeploying to change. A real flag system gives you:

1. Runtime control (change without deploy)
2. Targeting (per user, tenant, region)
3. Stable bucketing (same user, same variant)
4. Analytics (which variant performs better)
5. Audit (who changed what when)
6. Streaming updates (< 1s propagation)
7. Fallbacks (default if SDK can't reach server)
8. Multi-environment (dev/staging/prod isolation)

### Q2: How do feature flags affect testing?

**Answer:**

```
✗ Bad: write tests for `if FLAG: new(); else: old()` — exponential paths

✓ Good:
   1. Each branch has its own unit tests
   2. Integration test once with flag ON, once OFF
   3. Smoke tests in CI verify both code paths compile
   4. Don't combinatorially test 20 flags
      (use Pairwise testing for high-risk combos)

Senior advice: flag count > 30 = trouble.
   Aggressive cleanup is the only sustainable answer.
```

### Q3: How do you prevent flag-related bugs in production?

**Answer:**

```
1. Fail-open / fail-closed strategy
   ✓ Define for each flag what "default if SDK down" means
   ✓ Critical paths fail-open (feature ON)
   ✓ Risky paths fail-closed (feature OFF)

2. Local override for incident response
   ✓ Allow ops to override via env var or admin UI
   ✓ Don't depend solely on flag service

3. Monitor flag service health
   ✓ Alert if SDK can't fetch flags
   ✓ Alert if flag service > p99 latency

4. Test the kill switches
   ✓ Quarterly drill: flip kill switch in staging
   ✓ Verify rollback works

5. Code review for flag use
   ✓ Treat new flag as a deliberate decision
   ✓ Require owner + sunset date
```

### Q4: When is a feature flag the WRONG tool?

**Answer:**

```
✗ Permanent dead-code switch
   → Just delete the code

✗ Configuration that changes once a year
   → Use config file / env var

✗ Per-request routing (high-frequency decision)
   → Use load balancer / service mesh

✗ Security boundaries
   → Use RBAC, not flag
   → A flag is not a security control

✗ Replacing real testing
   → Flags don't validate correctness; tests do

✗ Hiding incomplete features users can find
   → Disable in UI, not just behind flag
```

### Q5: How do you do A/B testing the right way?

**Answer:**

```
Mistakes to avoid:
   ✗ Peeking at results early (statistical sin)
   ✗ Running with insufficient sample size
   ✗ Not defining the metric BEFORE the test
   ✗ Multiple comparisons without correction
   ✗ Selection bias in who sees the test

Correct flow:
   1. Hypothesis: "New checkout will increase conversion by X%"
   2. Power analysis: how many users needed?
      (depends on baseline rate + minimum detectable effect)
   3. Stable bucketing (hash-based)
   4. Run until sample size hit, OR define max duration
   5. Pre-registered metric (primary + secondaries)
   6. Statistical test (Bayesian or frequentist)
   7. Effect size + confidence interval reported
   8. If significant: roll out to 100%
   9. If not: kill flag, document learning
```

### Q6: Self-host vs SaaS for flag service?

**Answer:**

```
Self-host (Unleash, Flagsmith):
   ✓ No data leaves your environment
   ✓ Free (compute cost only)
   ✓ Customization
   ✗ Ops burden (high availability, scaling)
   ✗ Updates/security patches
   ✗ Build vs buy = 1-2 engineer-months/year

SaaS (LaunchDarkly, Split, ConfigCat):
   ✓ Zero ops
   ✓ Best-in-class UX
   ✓ Strong SDKs across languages
   ✗ Cost ($$$ at scale)
   ✗ Vendor lock-in (mitigated by OpenFeature)
   ✗ Data sent to third party (compliance check)

Rule of thumb:
   < 5M monthly evaluations    → SaaS (cheap tier)
   5M - 100M                   → SaaS or self-host
   > 100M                      → self-host (cost dominates)
   Strict data residency       → self-host
```

### Q7: How do flags interact with caches?

**Answer:**

```
Problem:
   Cache key: user.id + page.id → response
   Flag changes content → users see stale cached content

Solutions:

1. Include flag values in cache key
   key = f"{user.id}:{page.id}:{flag_a}:{flag_b}"
   ✗ Cache hit rate plummets

2. Vary by user segment, not by flag value
   key = f"{segment}:{page.id}"
   ✓ Segment changes only on flag promotion

3. Cache at component level
   ✓ Cache the parts that DON'T depend on flags
   ✓ Render flagged parts fresh

4. Short TTL for flag-affected responses
   ✓ Accept some inconsistency window

5. Cache-bypass header for opted-in users
   ✓ Internal/QA bypasses cache to test new variants
```

### Q8: How do you handle flag rollout for global services?

**Answer:**

```
Multi-region considerations:
   ✓ Roll out region-by-region
     IN (small market, fast feedback)
     → SG (APAC)
     → EU (compliance check)
     → US (highest stakes)

   ✓ Flag service must be globally available
     (regional read replicas)

   ✓ Targeting by region in flag rules:
     if region == "IN" and rollout_pct < 10 → ON

   ✓ Time-zone-aware rollouts
     Don't enable at peak US traffic on Friday
     Enable Monday 10am local time per region

   ✓ Monitor regional metrics separately
     A change OK in US may break in IN due to
     different user behavior, devices, networks
```

---

## Anti-Patterns

```
1. ✗ Flag spaghetti
   if A and B or not C and (D xor E)
   ✓ Refactor to clear states

2. ✗ Permanent "release" flags
   Flag at 100% for 6 months = dead code
   ✓ Remove after rollout complete

3. ✗ Per-request flag service calls
   Calling LaunchDarkly API on every request
   ✓ Use SDK with local cache (default behavior)

4. ✗ No fallback / default
   Flag service down → app crashes
   ✓ Always provide sane default

5. ✗ Flags as auth
   if FEATURE_ADMIN: do_admin_stuff
   ✓ Use proper RBAC, not flags

6. ✗ Random sampling instead of stable bucketing
   user.bucket = random() < 0.5
   ✓ user.bucket = hash(user.id) % 100 < 50

7. ✗ Testing only the new path
   Old path silently rots
   ✓ Test BOTH paths until flag is removed

8. ✗ Premature optimization with flags
   Flags everywhere "in case we need them"
   ✓ Add flags purposefully, with sunset
```

---

## Operational Checklist

```markdown
# Feature Flag Production Readiness

## Setup
- [ ] Flag service deployed (or SaaS selected)
- [ ] SDK integrated, fallback values defined
- [ ] OpenFeature wrapper for vendor-neutrality
- [ ] Type-safe flag registry in code

## Per-Flag
- [ ] Owner identified
- [ ] Sunset date set (for release/experiment flags)
- [ ] Targeting rules reviewed
- [ ] Default value defensible if SDK fails
- [ ] Both code paths tested

## Hygiene
- [ ] Weekly dashboard of stale flags
- [ ] Quarterly flag cleanup sprint
- [ ] CI guard: PR template requires flag metadata
- [ ] Grep CI fails if flag in code but not in service

## Observability
- [ ] Metric: flag evaluations per second
- [ ] Metric: SDK connection health
- [ ] Alert: SDK can't fetch (using fallbacks)
- [ ] Alert: flag service p99 latency

## Audit
- [ ] Who changed what flag when
- [ ] Approval workflow for production flag changes
- [ ] Export of all flags + rules for compliance
```

---

## Senior Mantras

```
1. Flags decouple DEPLOY from RELEASE. That's the superpower.

2. Every flag has an owner + a sunset date. No exceptions.

3. Stable bucketing — same user, same variant, always.

4. Default values matter more than people think.
   Plan what happens when flag service is down.

5. Treat flags as code: review, test, remove.

6. Ops flags (kill switches) are permanent. Document them.

7. Release flags are temporary. Removing them is the win condition.

8. A/B test results require pre-registered metrics + power analysis.

9. Don't use flags for security. Use RBAC.

10. Use OpenFeature to avoid vendor lock-in.
```

---

## Resources

```
✓ https://openfeature.dev — vendor-neutral standard
✓ https://docs.launchdarkly.com — industry standard docs
✓ https://www.getunleash.io — OSS flag service
✓ https://docs.growthbook.io — A/B testing focus
✓ https://www.flagsmith.com — OSS alternative
✓ https://posthog.com/docs/feature-flags — bundled with analytics
✓ "Feature Toggles" — Martin Fowler classic article
✓ "Build to Last" — Pete Hodgson on flag lifecycles
```

---

## Related Topics

- [11_deployment_decision_framework.md](11_deployment_decision_framework.md) — gradual rollouts
- [14_chaos_engineering.md](14_chaos_engineering.md) — kill switches complement chaos
- [15_multi_region_deployment.md](15_multi_region_deployment.md) — region-based rollouts
- [16_sre_practices_sli_slo.md](16_sre_practices_sli_slo.md) — auto-rollback on SLO breach
- [../Phase2_FastAPI/16_multi_tenant_architecture.md](../Phase2_FastAPI/16_multi_tenant_architecture.md) — tenant-scoped flags
- [../Phase3_Security/08_secrets_management_advanced.md](../Phase3_Security/08_secrets_management_advanced.md) — flags ≠ secrets
