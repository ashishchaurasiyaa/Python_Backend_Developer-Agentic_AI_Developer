"""
Feature Flags & Experimentation — Production Patterns
======================================================
Theory ground: 18_feature_flags_experimentation.md

Covers:
  1.  Flag type taxonomy and registry (with metadata, sunset dates, owners)
  2.  Stable bucketing — deterministic hash-based variant assignment
  3.  In-process flag evaluator with targeting rules
  4.  A/B experiment engine — exposure logging, conversion tracking
  5.  Gradual canary rollout state machine (1 → 10 → 50 → 100 %)
  6.  Circuit-breaker / auto-rollback wrapper
  7.  Permission (tier) flag pattern
  8.  Cache-key strategy helpers for flag-aware caching
  9.  Lifecycle hygiene — stale-flag audit, CI guard
  10. OpenFeature-style provider interface (illustrative, no pip needed)
  11. FastAPI dependency stubs (illustrative — no server started)
  12. Runnable __main__ demo — no external infra required

External libraries (all optional / illustrative — not required to run):
  # pip install openfeature-sdk
  # pip install UnleashClient
  # pip install fastapi uvicorn
"""

from __future__ import annotations

import hashlib
import logging
import time
import warnings
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ==========================================================================
# 1. FLAG TYPE TAXONOMY
# ==========================================================================

class FlagType(str, Enum):
    """
    The five canonical flag types from the theory.
    Each has a different expected lifespan and cleanup urgency.
    """
    RELEASE    = "release"     # ship dark code, enable later — HIGH cleanup urgency
    EXPERIMENT = "experiment"  # A/B test — HIGH cleanup urgency after analysis
    PERMISSION = "permission"  # tier / tenant gates — PERMANENT (lives forever)
    OPS        = "ops"         # kill switch / circuit breaker — PERMANENT
    CUSTOM     = "custom"      # tenant-specific config — varies


# ==========================================================================
# 2. FLAG REGISTRY — single source of truth
# ==========================================================================

@dataclass
class FlagDefinition:
    """
    Type-safe descriptor for one feature flag.
    Every flag MUST have an owner.
    Release and experiment flags MUST have a sunset_date.
    """
    name: str
    flag_type: FlagType
    default: Any                         # value when SDK cannot reach the server
    description: str
    owner: str                           # team or individual accountable for cleanup
    sunset_date: Optional[str] = None    # "YYYY-MM-DD" — required for release/experiment
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.flag_type in (FlagType.RELEASE, FlagType.EXPERIMENT):
            if self.sunset_date is None:
                raise ValueError(
                    f"Flag '{self.name}' (type={self.flag_type}) "
                    "must define a sunset_date. "
                    "Release and experiment flags are temporary — "
                    "set a deadline so they get cleaned up."
                )

    def is_stale(self, days_threshold: int = 30) -> bool:
        """
        Return True when a release/experiment flag is past its sunset date
        by more than days_threshold days.  Ops and permission flags never expire.
        """
        if self.flag_type not in (FlagType.RELEASE, FlagType.EXPERIMENT):
            return False
        if self.sunset_date is None:
            return False
        sunset = date.fromisoformat(self.sunset_date)
        delta = (date.today() - sunset).days
        return delta > days_threshold


# --- flag registry (the canonical list for this service) ---

FLAGS: Dict[str, FlagDefinition] = {
    f.name: f for f in [
        FlagDefinition(
            name="new_checkout_v2",
            flag_type=FlagType.RELEASE,
            default=False,
            description="Roll out the redesigned checkout flow.",
            owner="checkout-team",
            sunset_date="2026-07-01",
        ),
        FlagDefinition(
            name="homepage_layout_test",
            flag_type=FlagType.EXPERIMENT,
            default="control",
            description="A/B test: new homepage hero layout vs control.",
            owner="growth-team",
            sunset_date="2026-07-15",
            tags=["ab-test", "homepage"],
        ),
        FlagDefinition(
            name="feature_advanced_analytics",
            flag_type=FlagType.PERMISSION,
            default=False,
            description="Gate advanced analytics for pro/enterprise plans only.",
            owner="platform-team",
            # no sunset — permission flags are permanent
        ),
        FlagDefinition(
            name="disable_recommendations",
            flag_type=FlagType.OPS,
            default=False,
            description="Kill switch: disable recommendations service on incident.",
            owner="search-team",
            # no sunset — ops / kill-switch flags are permanent
        ),
        FlagDefinition(
            name="use_new_user_schema",
            flag_type=FlagType.RELEASE,
            default=False,
            description="Migrate DB reads/writes from v1 to v2 user table.",
            owner="data-team",
            sunset_date="2026-08-01",
        ),
    ]
}


# ==========================================================================
# 3. EVALUATION CONTEXT
# ==========================================================================

@dataclass
class EvaluationContext:
    """
    Holds the identity and attributes needed to evaluate targeting rules.
    Mirrors the OpenFeature EvaluationContext interface.
    """
    targeting_key: str                           # stable user/session identifier
    attributes: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.attributes.get(key, default)


# ==========================================================================
# 4. STABLE BUCKETING
# ==========================================================================

def compute_bucket(targeting_key: str, flag_name: str, total_buckets: int = 100) -> int:
    """
    Deterministic hash-based bucketing.

    Critical: the same user MUST see the same variant across every request.
    Using random() here would cause variant flickering — a known UX anti-pattern
    (see anti-pattern #6 in the theory doc).

    Algorithm:
      bucket = SHA-256(user_id + flag_name)[:8] as uint64  % total_buckets

    Including flag_name in the seed prevents all flags from splitting traffic
    at the same bucket boundary, which would create hidden correlations between
    experiments running simultaneously.
    """
    raw = f"{targeting_key}:{flag_name}".encode()
    digest = hashlib.sha256(raw).hexdigest()[:16]  # 64-bit hex prefix
    numeric = int(digest, 16)
    return numeric % total_buckets


def is_in_rollout(targeting_key: str, flag_name: str, percentage: int) -> bool:
    """
    Return True when the user falls inside the rollout percentage.
    Example: percentage=10 means roughly 10 % of users receive the flag.
    """
    if percentage <= 0:
        return False
    if percentage >= 100:
        return True
    return compute_bucket(targeting_key, flag_name) < percentage


# ==========================================================================
# 5. TARGETING RULES ENGINE
# ==========================================================================

# A targeting rule is a callable: (EvaluationContext) -> Optional[Any]
# If it matches, it returns the variant value.  If it does not match, None.
TargetingRule = Callable[[EvaluationContext], Optional[Any]]


def country_rule(countries: List[str], value: Any) -> TargetingRule:
    """Enable a flag for users in specific countries."""
    def _rule(ctx: EvaluationContext) -> Optional[Any]:
        if ctx.get("country") in countries:
            return value
        return None
    return _rule


def plan_rule(plans: List[str], value: Any) -> TargetingRule:
    """Enable a flag for users on specific subscription plans."""
    def _rule(ctx: EvaluationContext) -> Optional[Any]:
        if ctx.get("plan") in plans:
            return value
        return None
    return _rule


def rollout_percentage_rule(percentage: int, value: Any) -> TargetingRule:
    """Enable a flag for a stable percentage of users via hash bucketing."""
    def _rule(ctx: EvaluationContext) -> Optional[Any]:
        # flag_name is embedded via closure — unavailable here, so we use
        # the targeting_key alone.  In production, use compute_bucket directly.
        bucket = compute_bucket(ctx.targeting_key, "rollout_generic")
        if bucket < percentage:
            return value
        return None
    return _rule


def email_domain_rule(domain: str, value: Any) -> TargetingRule:
    """Enable a flag for internal employees (e.g. stage-1 canary to employees)."""
    def _rule(ctx: EvaluationContext) -> Optional[Any]:
        email: str = ctx.get("email", "")
        if email.endswith(f"@{domain}"):
            return value
        return None
    return _rule


# ==========================================================================
# 6. IN-PROCESS FLAG EVALUATOR (illustrative provider)
# ==========================================================================

class InMemoryFlagProvider:
    """
    A self-contained flag provider backed by an in-memory rule table.
    In production this would be replaced by LaunchDarkly / Unleash /
    GrowthBook via an OpenFeature-compatible provider.

    Key design principles (from theory):
      - Local evaluation — zero network call per check
      - Fallback to flag.default if flag is unknown
      - Rules evaluated in order; first match wins
    """

    def __init__(self) -> None:
        # {flag_name: [(rule, value), ...]}
        self._rules: Dict[str, List[TargetingRule]] = {}
        # {flag_name: Any}  — override for testing or incident response
        self._overrides: Dict[str, Any] = {}

    def add_rule(self, flag_name: str, rule: TargetingRule) -> None:
        self._rules.setdefault(flag_name, []).append(rule)

    def set_override(self, flag_name: str, value: Any) -> None:
        """
        Local override for incident response or integration tests.
        Ops staff can set env-var-based overrides without touching the flag service.
        Theory Q3: 'Allow ops to override via env var or admin UI.'
        """
        log.info("Flag override SET: %s = %r", flag_name, value)
        self._overrides[flag_name] = value

    def clear_override(self, flag_name: str) -> None:
        self._overrides.pop(flag_name, None)
        log.info("Flag override CLEARED: %s", flag_name)

    def evaluate(self, flag_name: str, ctx: EvaluationContext) -> Any:
        """
        Evaluate a flag for the given context.

        Resolution order:
          1. Local override (incident response)
          2. Targeting rules (first match wins)
          3. flag.default (fallback when nothing matches or flag unknown)
        """
        if flag_name in self._overrides:
            return self._overrides[flag_name]

        definition = FLAGS.get(flag_name)
        default = definition.default if definition is not None else None

        for rule in self._rules.get(flag_name, []):
            result = rule(ctx)
            if result is not None:
                return result

        return default

    def get_boolean(self, flag_name: str, default: bool, ctx: EvaluationContext) -> bool:
        value = self.evaluate(flag_name, ctx)
        if value is None:
            return default
        return bool(value)

    def get_string(self, flag_name: str, default: str, ctx: EvaluationContext) -> str:
        value = self.evaluate(flag_name, ctx)
        if value is None:
            return default
        return str(value)

    def get_integer(self, flag_name: str, default: int, ctx: EvaluationContext) -> int:
        value = self.evaluate(flag_name, ctx)
        if value is None:
            return default
        return int(value)


# ==========================================================================
# 7. TYPE-SAFE FLAG HELPERS (wrapping the registry)
# ==========================================================================

def is_on(
    flag: FlagDefinition,
    ctx: EvaluationContext,
    provider: InMemoryFlagProvider,
) -> bool:
    """
    Convenience wrapper used across the codebase.
    Centralising the call site makes it easy to swap providers later.
    """
    return provider.get_boolean(flag.name, bool(flag.default), ctx)


def variant_of(
    flag: FlagDefinition,
    ctx: EvaluationContext,
    provider: InMemoryFlagProvider,
) -> str:
    """Return the string variant for an experiment or multi-value flag."""
    return provider.get_string(flag.name, str(flag.default), ctx)


# ==========================================================================
# 8. A/B EXPERIMENT ENGINE
# ==========================================================================

@dataclass
class ExposureEvent:
    """
    An exposure event records which variant a user was assigned to.
    MUST be logged before any variant-specific rendering.
    Not logging exposures is a common analysis mistake that causes
    selection bias in the experiment results.
    """
    experiment: str
    variant: str
    user_id: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConversionEvent:
    """Records a primary metric event (e.g. purchase, sign-up)."""
    experiment: str
    variant: str
    user_id: str
    metric_name: str
    value: float = 1.0
    timestamp: float = field(default_factory=time.time)


class ExperimentEngine:
    """
    Handles stable variant assignment, exposure tracking, and
    conversion event collection for A/B tests.

    Correct A/B test flow (from theory Q5):
      1. Define hypothesis BEFORE starting
      2. Run power analysis to determine minimum sample size
      3. Hash-based stable bucketing
      4. Log exposures at moment of assignment
      5. Run until sample-size target — do NOT peek early
      6. Analyse with pre-registered primary metric
    """

    def __init__(self, provider: InMemoryFlagProvider) -> None:
        self._provider = provider
        self._exposures: List[ExposureEvent] = []
        self._conversions: List[ConversionEvent] = []

    def assign_variant(
        self,
        experiment_name: str,
        ctx: EvaluationContext,
        possible_variants: Optional[List[str]] = None,
    ) -> str:
        """
        Assign a stable variant to the user and record the exposure.
        The variant is driven by the flag provider, which in turn uses
        hash-based bucketing so the same user always gets the same variant.
        """
        definition = FLAGS.get(experiment_name)
        default_variant = str(definition.default) if definition else "control"

        variant = self._provider.get_string(experiment_name, default_variant, ctx)

        # Log exposure immediately — before any branch-specific rendering.
        event = ExposureEvent(
            experiment=experiment_name,
            variant=variant,
            user_id=ctx.targeting_key,
        )
        self._exposures.append(event)
        log.info(
            "EXPOSURE  experiment=%s  variant=%s  user=%s",
            experiment_name, variant, ctx.targeting_key,
        )
        return variant

    def record_conversion(
        self,
        experiment_name: str,
        variant: str,
        user_id: str,
        metric_name: str,
        value: float = 1.0,
    ) -> None:
        """
        Call this when the primary metric event occurs (e.g. purchase completed).
        In production, these events are sent to ClickHouse / BigQuery for analysis.
        """
        event = ConversionEvent(
            experiment=experiment_name,
            variant=variant,
            user_id=user_id,
            metric_name=metric_name,
            value=value,
        )
        self._conversions.append(event)
        log.info(
            "CONVERSION experiment=%s  variant=%s  user=%s  metric=%s  value=%.2f",
            experiment_name, variant, user_id, metric_name, value,
        )

    def summary(self, experiment_name: str) -> Dict[str, Any]:
        """
        Lightweight in-memory summary.  In production, run the ClickHouse
        query from the theory doc against the event warehouse.
        """
        exposures = [e for e in self._exposures if e.experiment == experiment_name]
        conversions = [c for c in self._conversions if c.experiment == experiment_name]

        result: Dict[str, Any] = {}
        variants_seen = {e.variant for e in exposures}

        for v in sorted(variants_seen):
            users = {e.user_id for e in exposures if e.variant == v}
            converters = {c.user_id for c in conversions if c.variant == v}
            n_users = len(users)
            n_conversions = len(converters)
            rate = n_conversions / n_users if n_users else 0.0
            result[v] = {
                "users": n_users,
                "conversions": n_conversions,
                "conversion_rate": round(rate, 4),
            }
        return result


# ==========================================================================
# 9. GRADUAL CANARY ROLLOUT STATE MACHINE
# ==========================================================================

class RolloutStage(Enum):
    """
    Canary rollout stages from the theory doc.
    The numeric value is the rollout percentage.
    """
    INTERNAL   = 0    # employees only (email domain rule)
    BETA       = 5    # beta-program opt-ins
    CANARY_1   = 1    # 1 % — watch error rates
    CANARY_10  = 10   # 10 % — watch p99 latency
    CANARY_50  = 50   # 50 % — A/B compare new vs old
    FULL       = 100  # fully rolled out
    REMOVED    = -1   # cleanup complete — flag deleted, code removed


@dataclass
class CanaryRollout:
    """
    Tracks the current stage of a gradual rollout.
    In production, stage transitions are driven by the flag service's
    percentage field.  This class models the logic in pure Python.
    """
    flag_name: str
    current_stage: RolloutStage = RolloutStage.INTERNAL
    stage_history: List[Dict[str, Any]] = field(default_factory=list)

    def advance(self, next_stage: RolloutStage) -> None:
        """
        Advance to the next rollout stage after metrics confirm stability.
        Always validate error rates and p99 latency before calling advance().
        """
        prev = self.current_stage
        self.current_stage = next_stage
        entry = {
            "from": prev.name,
            "to": next_stage.name,
            "percentage": next_stage.value,
            "timestamp": time.time(),
        }
        self.stage_history.append(entry)
        log.info(
            "ROLLOUT  flag=%s  %s → %s (%d%%)",
            self.flag_name, prev.name, next_stage.name, next_stage.value,
        )

    def is_enabled_for(self, ctx: EvaluationContext) -> bool:
        """
        Determine whether the flag is enabled for this context,
        based on the current canary stage.
        """
        stage = self.current_stage

        if stage == RolloutStage.REMOVED or stage.value < 0:
            return False

        if stage == RolloutStage.FULL:
            return True

        if stage == RolloutStage.INTERNAL:
            # Internal: employees only
            email: str = ctx.get("email", "")
            return email.endswith("@yourcompany.com")

        if stage == RolloutStage.BETA:
            # Beta: opted-in users
            return bool(ctx.get("beta_program", False))

        # Percentage-based stages (1 %, 10 %, 50 %)
        return is_in_rollout(ctx.targeting_key, self.flag_name, stage.value)


# ==========================================================================
# 10. CIRCUIT BREAKER / AUTO-ROLLBACK WRAPPER
# ==========================================================================

class ErrorRateTracker:
    """
    Minimal sliding-window error rate tracker.
    Production systems use Prometheus counters queried by the rule engine.
    """

    def __init__(self, window_seconds: int = 300) -> None:
        self._window = window_seconds
        self._events: List[Dict[str, Any]] = []

    def record(self, flag_name: str, success: bool) -> None:
        now = time.time()
        self._events.append({"flag": flag_name, "ok": success, "ts": now})
        # Prune old events
        cutoff = now - self._window
        self._events = [e for e in self._events if e["ts"] >= cutoff]

    def error_rate(self, flag_name: str) -> float:
        relevant = [e for e in self._events if e["flag"] == flag_name]
        if not relevant:
            return 0.0
        errors = sum(1 for e in relevant if not e["ok"])
        return errors / len(relevant)


class FlagWithCircuitBreaker:
    """
    Wraps a FlagDefinition with automatic rollback when the error rate
    exceeds a threshold.  Mirrors the pattern in the theory doc.

    If the error rate for this flag's code path exceeds error_threshold,
    the wrapper returns the safe default and emits an alert.
    """

    def __init__(
        self,
        flag: FlagDefinition,
        tracker: ErrorRateTracker,
        provider: InMemoryFlagProvider,
        error_threshold: float = 0.05,   # 5 % error rate triggers rollback
    ) -> None:
        self._flag = flag
        self._tracker = tracker
        self._provider = provider
        self._error_threshold = error_threshold
        self._auto_disabled = False

    def is_on(self, ctx: EvaluationContext) -> bool:
        current_rate = self._tracker.error_rate(self._flag.name)

        if current_rate > self._error_threshold:
            if not self._auto_disabled:
                self._auto_disabled = True
                self._alert(current_rate)
            # Fail-closed: return the safe default
            return bool(self._flag.default)

        # Normal path — let the provider evaluate
        self._auto_disabled = False
        return is_on(self._flag, ctx, self._provider)

    def _alert(self, error_rate: float) -> None:
        """In production, page the on-call engineer via PagerDuty / OpsGenie."""
        warnings.warn(
            f"AUTO-DISABLED flag '{self._flag.name}': "
            f"error rate {error_rate:.1%} exceeds threshold {self._error_threshold:.1%}. "
            "Falling back to default value.",
            stacklevel=2,
        )
        log.warning(
            "CIRCUIT OPEN  flag=%s  error_rate=%.2f%%  threshold=%.2f%%",
            self._flag.name, error_rate * 100, self._error_threshold * 100,
        )

    def record_outcome(self, success: bool) -> None:
        """Call after executing the flag-gated code path."""
        self._tracker.record(self._flag.name, success)


# ==========================================================================
# 11. PERMISSION FLAG PATTERN (tier / plan gating)
# ==========================================================================

class PermissionGate:
    """
    Evaluates a PERMISSION-type flag and raises an informative error
    when the user is not entitled.  Models the FastAPI dependency pattern
    from the theory doc without requiring an actual HTTP server.
    """

    def __init__(self, provider: InMemoryFlagProvider) -> None:
        self._provider = provider

    def require(self, flag: FlagDefinition, ctx: EvaluationContext) -> None:
        """
        Raise PermissionError when the user's plan does not entitle them
        to the feature.  In the FastAPI route this becomes HTTPException(403).

        In the flag service the rule is:
            feature_advanced_analytics = TRUE if plan IN ('pro', 'enterprise')
        Sales can grant access via the flag UI without a code change.
        """
        if not is_on(flag, ctx, self._provider):
            raise PermissionError(
                f"Feature '{flag.name}' is not available on your plan. "
                f"Upgrade to pro or enterprise to unlock it."
            )


# ==========================================================================
# 12. CACHE-KEY STRATEGY FOR FLAG-AWARE RESPONSES
# ==========================================================================

class FlagAwareCacheKey:
    """
    Helpers for including flag state in cache keys.

    The theory doc (Q7) discusses the cache-key problem:
      - Including raw flag values kills cache hit rate.
      - Better: segment users coarsely (e.g. plan tier), cache per segment.

    These helpers implement the theory doc's four strategies.
    """

    @staticmethod
    def include_flag_values(
        user_id: str,
        page_id: str,
        flag_values: Dict[str, Any],
    ) -> str:
        """
        Strategy 1: embed all flag values in the key.
        Simple but cache hit rate drops sharply when many flags are active.
        """
        flag_str = ":".join(f"{k}={v}" for k, v in sorted(flag_values.items()))
        return f"{user_id}:{page_id}:{flag_str}"

    @staticmethod
    def segment_based(
        segment: str,
        page_id: str,
    ) -> str:
        """
        Strategy 2: vary by user segment (e.g. 'pro', 'free', 'internal'),
        not by individual flag values.  Segment changes only on flag promotion,
        so the cache hit rate stays high between promotions.
        """
        return f"seg:{segment}:{page_id}"

    @staticmethod
    def component_level(
        component: str,
        page_id: str,
    ) -> str:
        """
        Strategy 3: cache only the components that do NOT depend on flags.
        Render flagged parts fresh every request.
        """
        return f"component:{component}:{page_id}"

    @staticmethod
    def bypass_header_value(user_id: str, secret: str) -> str:
        """
        Strategy 4: generate a cache-bypass token for internal/QA users
        so they can test new variants without serving stale content.
        """
        raw = f"{user_id}:{secret}".encode()
        return "bypass-" + hashlib.sha256(raw).hexdigest()[:12]


# ==========================================================================
# 13. FLAG LIFECYCLE HYGIENE — audit and CI guard
# ==========================================================================

def audit_stale_flags(
    flags: Dict[str, FlagDefinition],
    days_threshold: int = 30,
) -> List[FlagDefinition]:
    """
    Return flags that have passed their sunset date by more than days_threshold.

    In production, run this weekly and post results to Slack / Jira.
    Theory hygiene rule: every flag has a TTL or owner.
    Stale flags = bugs waiting to happen.
    """
    stale = [f for f in flags.values() if f.is_stale(days_threshold)]
    if stale:
        log.warning(
            "STALE FLAGS DETECTED (%d): %s",
            len(stale),
            [f.name for f in stale],
        )
    return stale


def ci_guard_flags(flags: Dict[str, FlagDefinition]) -> List[str]:
    """
    CI guard: fail the build if any release/experiment flag is missing a sunset_date.

    In practice, integrate this into a pytest fixture or a pre-commit hook.
    Returns a list of violation messages (empty = pass).
    """
    violations: List[str] = []
    for flag in flags.values():
        if flag.flag_type in (FlagType.RELEASE, FlagType.EXPERIMENT):
            if flag.sunset_date is None:
                violations.append(
                    f"  FAIL: '{flag.name}' ({flag.flag_type}) has no sunset_date. "
                    f"  Owner: {flag.owner}"
                )
    return violations


def check_flag_ownership(flags: Dict[str, FlagDefinition]) -> List[str]:
    """Return flags with empty or placeholder owners — another hygiene smell."""
    return [
        f.name for f in flags.values()
        if not f.owner or f.owner in ("", "unknown", "TBD")
    ]


# ==========================================================================
# 14. OPENFEATURE-STYLE PROVIDER INTERFACE (illustrative)
# ==========================================================================

class OpenFeatureProvider:
    """
    Illustrative skeleton of the OpenFeature provider contract.
    The real SDK is at https://openfeature.dev — install with:
        pip install openfeature-sdk

    By coding to this interface instead of a vendor SDK, you can swap
    between LaunchDarkly, Unleash, GrowthBook, etc. without changing
    application code (see OpenFeature: the vendor-neutral standard, theory doc).
    """

    def get_boolean_value(
        self,
        flag_key: str,
        default_value: bool,
        ctx: Optional[EvaluationContext] = None,
    ) -> bool:
        raise NotImplementedError

    def get_string_value(
        self,
        flag_key: str,
        default_value: str,
        ctx: Optional[EvaluationContext] = None,
    ) -> str:
        raise NotImplementedError

    def get_integer_value(
        self,
        flag_key: str,
        default_value: int,
        ctx: Optional[EvaluationContext] = None,
    ) -> int:
        raise NotImplementedError

    def get_object_value(
        self,
        flag_key: str,
        default_value: Dict[str, Any],
        ctx: Optional[EvaluationContext] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError


class InMemoryOpenFeatureProvider(OpenFeatureProvider):
    """
    Concrete OpenFeature provider backed by InMemoryFlagProvider.
    Drop-in for unit tests or local dev without an external flag service.
    """

    def __init__(self, inner: InMemoryFlagProvider) -> None:
        self._inner = inner

    def get_boolean_value(
        self,
        flag_key: str,
        default_value: bool,
        ctx: Optional[EvaluationContext] = None,
    ) -> bool:
        if ctx is None:
            ctx = EvaluationContext(targeting_key="anonymous")
        return self._inner.get_boolean(flag_key, default_value, ctx)

    def get_string_value(
        self,
        flag_key: str,
        default_value: str,
        ctx: Optional[EvaluationContext] = None,
    ) -> str:
        if ctx is None:
            ctx = EvaluationContext(targeting_key="anonymous")
        return self._inner.get_string(flag_key, default_value, ctx)

    def get_integer_value(
        self,
        flag_key: str,
        default_value: int,
        ctx: Optional[EvaluationContext] = None,
    ) -> int:
        if ctx is None:
            ctx = EvaluationContext(targeting_key="anonymous")
        return self._inner.get_integer(flag_key, default_value, ctx)

    def get_object_value(
        self,
        flag_key: str,
        default_value: Dict[str, Any],
        ctx: Optional[EvaluationContext] = None,
    ) -> Dict[str, Any]:
        if ctx is None:
            ctx = EvaluationContext(targeting_key="anonymous")
        value = self._inner.evaluate(flag_key, ctx)
        if isinstance(value, dict):
            return value
        return default_value


# ==========================================================================
# 15. FASTAPI DEPENDENCY STUBS (illustrative — no server started)
# ==========================================================================

FASTAPI_DEPS_EXAMPLE = '''
# deps.py — FastAPI dependency injection for feature flags
# (requires: pip install fastapi)

from fastapi import Depends, Request, HTTPException

_provider = InMemoryFlagProvider()
_of_provider = InMemoryOpenFeatureProvider(_provider)


def get_flag_provider() -> OpenFeatureProvider:
    """Inject the flag provider as a FastAPI dependency."""
    return _of_provider


def get_flag_context(request: Request) -> EvaluationContext:
    """
    Build an EvaluationContext from the incoming HTTP request.
    In a real app, also decode the JWT to get user.plan, user.country etc.
    """
    user_id = request.headers.get("X-User-ID", request.client.host)
    return EvaluationContext(
        targeting_key=user_id,
        attributes={
            "country":     request.headers.get("X-Country", "unknown"),
            "plan":        request.headers.get("X-Plan", "free"),
            "app_version": request.headers.get("X-App-Version", "unknown"),
        },
    )


# --- route examples ---

# @app.get("/checkout")
# async def checkout(
#     flags: OpenFeatureProvider = Depends(get_flag_provider),
#     ctx: EvaluationContext     = Depends(get_flag_context),
# ):
#     if flags.get_boolean_value("new_checkout_v2", False, ctx):
#         return await new_checkout_flow()
#     layout = flags.get_string_value("checkout_layout", "default", ctx)
#     return await checkout_with_layout(layout)


# @app.get("/recommendations")
# async def recommendations(
#     flags: OpenFeatureProvider = Depends(get_flag_provider),
#     ctx: EvaluationContext     = Depends(get_flag_context),
# ):
#     # OPS kill switch
#     if flags.get_boolean_value("disable_recommendations", False, ctx):
#         return {"recommendations": [], "reason": "temporarily_disabled"}
#     return await fetch_recommendations()


# @app.post("/api/advanced-feature")
# async def advanced(
#     flags: OpenFeatureProvider = Depends(get_flag_provider),
#     ctx: EvaluationContext     = Depends(get_flag_context),
# ):
#     if not flags.get_boolean_value("feature_advanced_analytics", False, ctx):
#         raise HTTPException(403, "Not available on your plan")
#     return await advanced_logic()
'''


# ==========================================================================
# 16. RUNNABLE __main__ DEMO
# ==========================================================================

def _build_demo_provider() -> InMemoryFlagProvider:
    """Construct a provider with targeting rules matching the theory examples."""
    provider = InMemoryFlagProvider()

    # new_checkout_v2: enabled for pro + enterprise users
    provider.add_rule(
        "new_checkout_v2",
        plan_rule(["pro", "enterprise"], True),
    )

    # homepage_layout_test: multi-variant A/B test via stable bucketing
    # In practice the provider handles this; here we show the logic explicitly.
    def _homepage_variant(ctx: EvaluationContext) -> Optional[str]:
        bucket = compute_bucket(ctx.targeting_key, "homepage_layout_test")
        if bucket < 33:
            return "control"
        if bucket < 66:
            return "variant_a"
        return "variant_b"

    provider.add_rule("homepage_layout_test", _homepage_variant)

    # feature_advanced_analytics: pro and enterprise plans only
    provider.add_rule(
        "feature_advanced_analytics",
        plan_rule(["pro", "enterprise"], True),
    )

    # disable_recommendations: default False (ops flag — only set via override)
    # No targeting rule: defaults to False unless overridden at runtime.

    # use_new_user_schema: 10 % rollout
    provider.add_rule(
        "use_new_user_schema",
        rollout_percentage_rule(10, True),
    )

    return provider


def _demo_stable_bucketing() -> None:
    print("\n--- Stable Bucketing ---")
    user_ids = ["user-001", "user-002", "user-003", "alice", "bob"]
    flag_name = "homepage_layout_test"
    for uid in user_ids:
        b = compute_bucket(uid, flag_name)
        print(f"  {uid:12s}  bucket={b:3d}  in_10pct={is_in_rollout(uid, flag_name, 10)}")


def _demo_flag_evaluation(provider: InMemoryFlagProvider) -> None:
    print("\n--- Flag Evaluation ---")

    users = [
        EvaluationContext("user-free",  {"plan": "free",       "email": "alice@external.com"}),
        EvaluationContext("user-pro",   {"plan": "pro",        "email": "bob@external.com"}),
        EvaluationContext("user-ent",   {"plan": "enterprise", "email": "carol@yourcompany.com"}),
        EvaluationContext("user-employee", {"plan": "free",    "email": "dev@yourcompany.com"}),
    ]

    flag = FLAGS["new_checkout_v2"]
    for ctx in users:
        enabled = is_on(flag, ctx, provider)
        print(f"  {ctx.targeting_key:18s}  plan={ctx.get('plan'):12s}  new_checkout={enabled}")


def _demo_ops_kill_switch(provider: InMemoryFlagProvider) -> None:
    print("\n--- Ops Kill Switch ---")
    ctx = EvaluationContext("user-123", {"plan": "pro"})
    flag_name = "disable_recommendations"

    def serve_recommendations(ctx_: EvaluationContext) -> str:
        if provider.get_boolean(flag_name, False, ctx_):
            return "DISABLED — service under incident"
        return "Serving live recommendations"

    print(f"  Before override: {serve_recommendations(ctx)}")
    provider.set_override(flag_name, True)    # incident: flip kill switch
    print(f"  After override:  {serve_recommendations(ctx)}")
    provider.clear_override(flag_name)        # incident resolved
    print(f"  After clearing:  {serve_recommendations(ctx)}")


def _demo_ab_experiment(provider: InMemoryFlagProvider) -> None:
    print("\n--- A/B Experiment ---")
    engine = ExperimentEngine(provider)
    experiment = "homepage_layout_test"

    # Simulate 12 users visiting the homepage
    user_ids = [f"user-{i:03d}" for i in range(12)]
    assignments: Dict[str, str] = {}

    for uid in user_ids:
        ctx = EvaluationContext(uid, {"plan": "free"})
        variant = engine.assign_variant(experiment, ctx)
        assignments[uid] = variant

    # Simulate conversions: variant_b performs better
    for uid, variant in assignments.items():
        if variant == "control" and hash(uid) % 5 == 0:
            engine.record_conversion(experiment, variant, uid, "click")
        elif variant == "variant_a" and hash(uid) % 4 == 0:
            engine.record_conversion(experiment, variant, uid, "click")
        elif variant == "variant_b" and hash(uid) % 3 == 0:
            engine.record_conversion(experiment, variant, uid, "click")

    summary = engine.summary(experiment)
    print(f"\n  Experiment results for '{experiment}':")
    for variant, stats in summary.items():
        print(
            f"    {variant:12s}  users={stats['users']:3d}  "
            f"conversions={stats['conversions']:2d}  "
            f"rate={stats['conversion_rate']:.1%}"
        )


def _demo_canary_rollout() -> None:
    print("\n--- Canary Rollout State Machine ---")
    rollout = CanaryRollout(flag_name="new_checkout_v2")

    internal_user = EvaluationContext("emp-001", {"email": "engineer@yourcompany.com", "plan": "free"})
    external_user = EvaluationContext("usr-999", {"email": "customer@gmail.com",       "plan": "pro"})

    stages = [
        RolloutStage.INTERNAL,
        RolloutStage.BETA,
        RolloutStage.CANARY_1,
        RolloutStage.CANARY_10,
        RolloutStage.CANARY_50,
        RolloutStage.FULL,
    ]

    for stage in stages:
        rollout.current_stage = stage
        internal_enabled = rollout.is_enabled_for(internal_user)
        external_enabled = rollout.is_enabled_for(external_user)
        print(
            f"  Stage {stage.name:12s} ({stage.value:3}%)  "
            f"employee={internal_enabled}  external_user={external_enabled}"
        )

    # Demonstrate state transition logging
    rollout.current_stage = RolloutStage.CANARY_1
    rollout.advance(RolloutStage.CANARY_10)


def _demo_circuit_breaker(provider: InMemoryFlagProvider) -> None:
    print("\n--- Circuit Breaker / Auto-Rollback ---")
    flag = FLAGS["new_checkout_v2"]
    tracker = ErrorRateTracker(window_seconds=60)
    breaker = FlagWithCircuitBreaker(flag, tracker, provider, error_threshold=0.05)

    ctx = EvaluationContext("user-pro", {"plan": "pro"})

    print("  Simulating healthy traffic (no errors):")
    for _ in range(10):
        breaker.record_outcome(success=True)
    print(f"  Error rate: {tracker.error_rate(flag.name):.1%}  flag on: {breaker.is_on(ctx)}")

    print("\n  Simulating error spike (8/10 failures):")
    for i in range(10):
        breaker.record_outcome(success=(i >= 8))
    print(f"  Error rate: {tracker.error_rate(flag.name):.1%}  flag on: {breaker.is_on(ctx)}")


def _demo_permission_gate(provider: InMemoryFlagProvider) -> None:
    print("\n--- Permission Gate (plan-based) ---")
    gate = PermissionGate(provider)
    flag = FLAGS["feature_advanced_analytics"]

    contexts = [
        EvaluationContext("free-user",  {"plan": "free"}),
        EvaluationContext("pro-user",   {"plan": "pro"}),
        EvaluationContext("ent-user",   {"plan": "enterprise"}),
    ]

    for ctx in contexts:
        try:
            gate.require(flag, ctx)
            print(f"  {ctx.targeting_key:12s}  plan={ctx.get('plan'):12s}  GRANTED")
        except PermissionError as exc:
            print(f"  {ctx.targeting_key:12s}  plan={ctx.get('plan'):12s}  DENIED — {exc}")


def _demo_cache_keys() -> None:
    print("\n--- Cache Key Strategies ---")
    flag_values = {"new_checkout_v2": True, "homepage_layout_test": "variant_a"}

    k1 = FlagAwareCacheKey.include_flag_values("usr-1", "home", flag_values)
    k2 = FlagAwareCacheKey.segment_based("pro", "home")
    k3 = FlagAwareCacheKey.component_level("hero_banner", "home")
    k4 = FlagAwareCacheKey.bypass_header_value("usr-1", "internal-secret")

    print(f"  Strategy 1 (flag values in key): {k1}")
    print(f"  Strategy 2 (segment-based):      {k2}")
    print(f"  Strategy 3 (component-level):    {k3}")
    print(f"  Strategy 4 (bypass token):        {k4}")


def _demo_lifecycle_hygiene() -> None:
    print("\n--- Lifecycle Hygiene ---")

    # Add an intentionally stale flag to show detection
    stale_flag = FlagDefinition(
        name="old_feature_removed_flag",
        flag_type=FlagType.RELEASE,
        default=False,
        description="Should have been removed months ago.",
        owner="ex-employee-team",
        sunset_date="2024-01-01",   # deliberately far in the past
    )
    test_registry = dict(FLAGS)
    test_registry[stale_flag.name] = stale_flag

    stale = audit_stale_flags(test_registry, days_threshold=30)
    print(f"  Stale flags detected: {[f.name for f in stale]}")

    violations = ci_guard_flags(FLAGS)
    if violations:
        print("  CI violations:\n" + "\n".join(violations))
    else:
        print("  CI guard PASSED — all release/experiment flags have sunset_date")

    orphans = check_flag_ownership(FLAGS)
    if orphans:
        print(f"  Ownership check FAILED: {orphans}")
    else:
        print("  Ownership check PASSED — all flags have an owner")


if __name__ == "__main__":
    print("=" * 70)
    print("Feature Flags & Experimentation — Runnable Demo")
    print("=" * 70)

    provider = _build_demo_provider()

    _demo_stable_bucketing()
    _demo_flag_evaluation(provider)
    _demo_ops_kill_switch(provider)
    _demo_ab_experiment(provider)
    _demo_canary_rollout()
    _demo_circuit_breaker(provider)
    _demo_permission_gate(provider)
    _demo_cache_keys()
    _demo_lifecycle_hygiene()

    print("\n" + "=" * 70)
    print("Demo complete.  All sections ran without external infrastructure.")
    print("=" * 70)
