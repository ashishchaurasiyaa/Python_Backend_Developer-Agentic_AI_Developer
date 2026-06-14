"""
Django Middleware Hooks, Signals vs save(), Model Validation, Cache, Testing & Deployment Gaps

Production-grade illustration of the concepts most commonly misunderstood at the "Django works"
→ "Django works in production" boundary:

  - Middleware hook order: __call__, process_view, process_exception, process_template_response
  - Middleware short-circuiting and the onion model
  - Field lookups: systematic table, get() exception handling, queryset set operations (union/intersection/difference)
  - save() override pitfalls: bulk-ops bypass, recursion, update_fields, signals double-fire
  - Model validation: clean() / full_clean() — when it fires and when it does NOT
  - Signals: dispatch_uid, hidden control flow, bulk-ops gap, save-override vs signal vs service-layer decision
  - Django cache framework: per-view, low-level API, cached_property, invalidation patterns
  - TestCase vs TransactionTestCase: on_commit, captureOnCommitCallbacks, setUpTestData vs setUp
  - Auth internals: authenticate(), login() session-fixation protection, logout()
  - Deployment gaps: WhiteNoise, DEBUG=False checklist, SECURE_* settings

This module is IMPORTABLE production-pattern code — no runnable __main__ block is provided
because all patterns depend on a configured Django project (settings, DB, cache backend).
Each section is a self-contained, copy-paste-ready snippet with inline commentary.

References:
  https://docs.djangoproject.com/en/5.0/topics/http/middleware/
  https://docs.djangoproject.com/en/5.0/ref/models/querysets/
  https://docs.djangoproject.com/en/5.0/topics/signals/
  https://docs.djangoproject.com/en/5.0/topics/cache/
  https://docs.djangoproject.com/en/5.0/topics/testing/tools/
  https://whitenoise.readthedocs.io/
"""

# pip install django djangorestframework whitenoise
# Optional for structured logging:  pip install structlog

from __future__ import annotations

import logging
import time
from decimal import Decimal
from functools import wraps

logger = logging.getLogger(__name__)


# ==========================================================================
# 1. MIDDLEWARE HOOKS — COMPLETE REFERENCE
# ==========================================================================
#
# Hook execution order (MIDDLEWARE = [A, B, C]):
#
# REQUEST  ──► A.__call__ pre-phase
#                  B.__call__ pre-phase
#                      C.__call__ pre-phase
#                      ── URL resolution ──
#                      A.process_view → B.process_view → C.process_view   (top-down)
#                      ┌──────────────────┐
#                      │       VIEW       │
#                      └──────────────────┘
#                      exception → C.process_exception → B → A            (bottom-up)
#                      TemplateResponse → C.process_template_response → B → A (bottom-up)
#                  C.__call__ post-phase
#              B.__call__ post-phase
# RESPONSE ◄── A.__call__ post-phase
#
# Mental model: onion — request travels inward (list order), response outward (reverse).
# process_view is request-side (top-down); process_exception + process_template_response
# are response-side (bottom-up).

try:
    from django.http import HttpRequest, HttpResponse
    from django.template.response import TemplateResponse
except ImportError:
    # Allow py_compile to succeed without Django installed
    HttpRequest = object
    HttpResponse = object
    TemplateResponse = object


# --------------------------------------------------------------------------
# 1a. Timing middleware — demonstrates all 5 hooks
# --------------------------------------------------------------------------

class TimingAndAuditMiddleware:
    """
    Production-ready middleware demonstrating every hook and its role.

    - __init__: runs ONCE at server start — safe for expensive setup (config load, SDK init).
    - __call__: wraps every request/response; monotonic timer for X-Duration-Ms header.
    - process_view: called after URL resolution, before the view — lets you inspect the
                    resolved view function (e.g. read custom attributes set by decorators).
    - process_exception: called only when the view raises an uncaught exception.
                         This is EXACTLY where Sentry hooks in — zero view-code changes.
    - process_template_response: called only when response has a .render() method
                                  (TemplateResponse) and the template is NOT yet rendered.
                                  Mutate context_data here, not in the view.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Heavy one-time setup goes here: load config, initialise SDK clients, etc.
        logger.info("TimingAndAuditMiddleware initialised (runs once per server start)")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # ── REQUEST PHASE ────────────────────────────────────────────────
        request.start_time = time.monotonic()

        response = self.get_response(request)   # calls the next middleware / view

        # ── RESPONSE PHASE ───────────────────────────────────────────────
        duration_ms = (time.monotonic() - request.start_time) * 1000
        response["X-Duration-Ms"] = f"{duration_ms:.2f}"
        return response

    def process_view(self, request: HttpRequest, view_func, view_args, view_kwargs):
        """
        Called AFTER URL resolution but BEFORE the view executes.
        This is the only point where you know WHICH view will run.

        In __call__'s request phase, URL resolution has not happened yet — you cannot
        know the view function there.  Use process_view for:
          - Inspecting decorator-set attributes (CSRF middleware checks csrf_exempt here).
          - Per-view rate limiting or maintenance mode using the resolved view name.
          - Skipping audit for views decorated with @skip_audit.

        Return None to let the chain continue; return an HttpResponse to short-circuit
        (skip the view and all lower middleware process_view calls).
        """
        if getattr(view_func, "skip_audit", False):
            request._skip_audit = True
        return None  # continue

    def process_exception(self, request: HttpRequest, exception: Exception):
        """
        Called when the view raises an uncaught exception (including Http404).

        Sentry, Rollbar, and similar tools hook here — they capture the exception
        with full context, then return None so Django's normal 500 handling still runs.

        Return None  → Django continues with its 500 / DEBUG traceback page.
        Return HttpResponse → that response is sent instead (custom error page).
        """
        logger.exception(
            "Unhandled exception at %s",
            request.path,
            exc_info=exception,
            extra={"user_id": getattr(getattr(request, "user", None), "pk", None)},
        )
        return None  # let Django render its 500 page

    def process_template_response(self, request: HttpRequest, response):
        """
        Called ONLY for TemplateResponse objects — the template has NOT been rendered yet.
        This is the safe place to inject global context (banners, feature flags, etc.)
        without touching individual views.

        Must always return the response (optionally mutated).
        """
        if hasattr(response, "context_data") and response.context_data is not None:
            response.context_data.setdefault("global_banner", _get_global_banner())
        return response


def _get_global_banner() -> str | None:
    """Placeholder for a real banner lookup (e.g. from cache or DB)."""
    return None


# --------------------------------------------------------------------------
# 1b. Short-circuiting middleware
# --------------------------------------------------------------------------

class MaintenanceModeMiddleware:
    """
    Demonstrates short-circuiting: returning an HttpResponse WITHOUT calling
    self.get_response() skips everything below in the chain (lower middleware + view).

    Critical insight: middleware ABOVE (earlier in the list) that already passed
    the request-phase will still run their RESPONSE phase — they are on the outer
    layers of the onion and the response must pass through them on the way out.

    This is why SecurityMiddleware is placed FIRST in MIDDLEWARE: even short-circuited
    responses pass through its response phase and receive security headers.
    """

    MAINTENANCE_BYPASS_HEADER = "X-Maintenance-Token"

    def __init__(self, get_response):
        self.get_response = get_response
        self._maintenance_active = False  # in production: read from cache/settings

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if self._maintenance_active:
            bypass_token = request.headers.get(self.MAINTENANCE_BYPASS_HEADER, "")
            if bypass_token != "internal-secret":
                # Short-circuit: get_response() never called → view and lower middleware skipped.
                return HttpResponse("Service under maintenance. Back soon.", status=503)
        return self.get_response(request)


# --------------------------------------------------------------------------
# 1c. process_view — CSRF-style attribute inspection
# --------------------------------------------------------------------------

def skip_audit(view_func):
    """
    Decorator that sets a flag on the view function.
    TimingAndAuditMiddleware.process_view() checks this flag.
    This is the EXACT pattern Django's own CSRF middleware uses for @csrf_exempt.
    """
    view_func.skip_audit = True

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)

    wrapper.skip_audit = True
    return wrapper


# ==========================================================================
# 2. FIELD LOOKUPS — SYSTEMATIC REFERENCE
# ==========================================================================

# Lookup        SQL approximation           Notes
# ─────────────────────────────────────────────────────────────────────────
# __exact       = 'x'                       Default — filter(name='x') == name__exact
# __iexact      ILIKE 'x'                   Case-insensitive equality, no wildcard
# __contains    LIKE '%x%'                  Cannot use index (leading %)
# __icontains   ILIKE '%x%'                 Case-insensitive substring, no index
# __in          IN (1,2,3)                  Accepts a list OR a queryset (subquery)
# __gt/gte      > / >=                      Works on dates, decimals, integers
# __lt/lte      < / <=
# __startswith  LIKE 'x%'                   Trailing % → index CAN be used
# __istartswith ILIKE 'x%'
# __endswith    LIKE '%x'                   Leading % → no index
# __range=(a,b) BETWEEN a AND b             Both bounds inclusive
# __date        DATE(column) = date         Extract date part from DateTimeField
# __year/__month/__day                      Individual date component extraction
# __isnull=True IS NULL                     Correct way to filter None values
# ─────────────────────────────────────────────────────────────────────────

LOOKUP_EXAMPLES = """
# These snippets assume a Django ORM environment with an app already configured.

from blog.models import Post, Author
from datetime import date
from django.db.models import Q

# ── Exact and case-insensitive exact ──────────────────────────────────────
Post.objects.filter(title__iexact='django tips')

# ── Range and date extraction ─────────────────────────────────────────────
Post.objects.filter(views__gte=100, views__lt=1000)
Post.objects.filter(created_at__date=date(2026, 6, 12))
Post.objects.filter(created_at__year=2026)

# ── Multiple kwargs in one filter() = SQL AND ─────────────────────────────
Post.objects.filter(status='published', views__gte=100)

# ── Traverse related fields with double-underscore ────────────────────────
Post.objects.filter(author__profile__city__iexact='mumbai')

# ── __in with a queryset = single SQL subquery (NOT two round trips) ──────
hot_authors = Author.objects.filter(score__gte=90)
Post.objects.filter(author__in=hot_authors)

# ── __isnull — correct pattern for NULL checks ───────────────────────────
Post.objects.filter(published_at__isnull=True)    # draft posts
"""


# --------------------------------------------------------------------------
# 2a. get() exception handling — all three patterns
# --------------------------------------------------------------------------

GET_PATTERNS = """
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

User = get_user_model()

# Pattern 1: explicit exception handling — both failure modes
try:
    user = User.objects.get(email='a@b.com')
except User.DoesNotExist:
    # 0 rows — handle gracefully
    user = None
except User.MultipleObjectsReturned:
    # 2+ rows — this is a data-integrity bug; handle AND add a DB constraint
    user = User.objects.filter(email='a@b.com').order_by('id').first()
    logger.error('Duplicate emails found — add UniqueConstraint on User.email!')

# Pattern 2: 404 in views — avoid manual try/except boilerplate
user = get_object_or_404(User, email='a@b.com')   # DoesNotExist → Http404

# Pattern 3: "give me None if missing" — no exception raised
user = User.objects.filter(email='a@b.com').first()  # None when missing

# NOTE: prefer model-specific User.DoesNotExist over generic ObjectDoesNotExist.
# The generic form can silently swallow DoesNotExist from nested queries for OTHER
# models, hiding bugs.
"""


# --------------------------------------------------------------------------
# 2b. QuerySet set operations: union, intersection, difference
# --------------------------------------------------------------------------

SET_OPERATION_EXAMPLES = """
from blog.models import Post, Draft

qs1 = Post.objects.filter(status='published').values_list('author_id', 'title')
qs2 = Draft.objects.filter(ready=True).values_list('author_id', 'title')

# UNION — removes duplicates (DISTINCT); columns and types MUST match
combined = qs1.union(qs2)

# UNION ALL — keeps duplicates; much faster on large result sets
combined_all = qs1.union(qs2, all=True)

# INTERSECTION — rows present in BOTH querysets
common = qs1.intersection(qs2)

# DIFFERENCE — rows in qs1 but NOT in qs2
only_published = qs1.difference(qs2)

# ── CRITICAL LIMITATIONS (asked in every senior interview) ────────────────
# After union/intersection/difference you can ONLY use order_by() and slicing.
# filter(), annotate(), aggregate() raise NotSupportedError.

combined.order_by('title')[:10]    # OK  — LIMIT/OFFSET + ORDER BY
# combined.filter(author_id=5)     # RAISES NotSupportedError — do NOT do this

# Apply filters BEFORE the set operation, not after:
qs1_filtered = Post.objects.filter(status='published', views__gte=100)\\
                            .values_list('author_id', 'title')
result = qs1_filtered.union(qs2)

# ── union() vs Q-object OR ────────────────────────────────────────────────
# Same model, need further filtering after combining → use Q objects (not union):
from django.db.models import Q
Post.objects.filter(Q(status='published') | Q(author_id=1)).filter(views__gte=10)
# Q | Q stays as a single queryset — fully composable.

# Different models OR both branches already distinct/annotated → union() is correct.
"""


# ==========================================================================
# 3. save() OVERRIDE — PITFALLS AND CORRECT PATTERNS
# ==========================================================================

try:
    from django.db import models
    from django.utils.text import slugify
    _DJANGO_AVAILABLE = True
except ImportError:
    _DJANGO_AVAILABLE = False
    # Stub so the file remains importable and py_compile succeeds
    class models:  # type: ignore[no-redef]
        class Model:
            pass
        class DecimalField:
            def __init__(self, *a, **kw): pass
        class CharField:
            def __init__(self, *a, **kw): pass
        class DateField:
            def __init__(self, *a, **kw): pass
        class ForeignKey:
            def __init__(self, *a, **kw): pass
        CASCADE = None
        class Manager:
            pass


if _DJANGO_AVAILABLE:
    from django.db import models as _real_models

    class Order(_real_models.Model):
        """
        Demonstrates the correct save() override pattern and all four pitfalls.
        """

        subtotal = _real_models.DecimalField(max_digits=10, decimal_places=2)
        tax = _real_models.DecimalField(max_digits=10, decimal_places=2, default=0)
        status = _real_models.CharField(max_length=20, default="pending")

        def save(self, *args, **kwargs):
            # ── Pitfall 3 fix: respect update_fields ──────────────────────
            # If the caller specified update_fields, our derived field 'tax'
            # must be added to the set or it will be silently omitted from SQL.
            uf = kwargs.get("update_fields")
            self.tax = self.subtotal * Decimal("0.18")
            if uf is not None:
                kwargs["update_fields"] = set(uf) | {"tax"}

            # ── Always call super() — forgetting this means NOTHING is saved ──
            super().save(*args, **kwargs)
            # ── Pitfall 2 fix: do NOT call self.save() here ───────────────
            # If post-save work is needed, use update() on the queryset:
            #   Order.objects.filter(pk=self.pk).update(processed=True)

        class Meta:
            app_label = "blog"  # satisfy Django's app registry in a standalone file

    class Article(_real_models.Model):
        """Demonstrates slug derivation — a valid use of save() override."""

        title = _real_models.CharField(max_length=200)
        slug = _real_models.CharField(max_length=220, blank=True)

        def save(self, *args, **kwargs):
            if not self.slug:
                self.slug = slugify(self.title)
            super().save(*args, **kwargs)

        class Meta:
            app_label = "blog"


# --------------------------------------------------------------------------
# Pitfall summary (inline reference)
# --------------------------------------------------------------------------

SAVE_OVERRIDE_PITFALLS = """
PITFALL 1 — Bulk operations bypass save() entirely:
    Order.objects.filter(...).update(subtotal=500)   # save() NOT called — tax stays stale!
    Order.objects.bulk_create([...])                 # save() NOT called (signals skipped too)
    Order.objects.bulk_update(orders, ['subtotal'])  # same

    Fix: for invariants that MUST survive bulk paths, use DB-level enforcement:
         GeneratedField (Django 5+), CheckConstraint, or a database trigger.

PITFALL 2 — Recursive save() calls:
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.processed = True
        self.save()           # INFINITE RECURSION — save() calls itself again
    Fix: set self.processed = True BEFORE super().save(), or use:
         Order.objects.filter(pk=self.pk).update(processed=True)  after super().

PITFALL 3 — Ignoring update_fields:
    order.save(update_fields=['status'])
    # If your override modifies 'tax' but does not add 'tax' to update_fields,
    # the tax change never reaches the database.
    Fix: in save(), always merge your derived fields into the update_fields set
         (see Order.save() above).

PITFALL 4 — Signals double-fire:
    Calling super().save() twice inside one override fires pre_save/post_save twice.
    If a signal sends an email, you get duplicate emails.
    Fix: call super().save() exactly once per save() invocation.

DECISION FRAMEWORK:
    Derived field on YOUR model (slug, tax)   → save() override
    React to a THIRD-PARTY model (auth.User)  → Signal (only option)
    Multi-model business flow (order → email) → Service function (explicit, testable)
    Invariant that bulk ops must also honour   → DB constraint / GeneratedField / trigger
"""


# ==========================================================================
# 4. MODEL VALIDATION — clean() / full_clean() — THE CLASSIC TRAP
# ==========================================================================

if _DJANGO_AVAILABLE:
    from django.core.exceptions import ValidationError

    class Booking(_real_models.Model):
        """
        Illustrates clean() for cross-field validation and the full_clean() trap.
        """

        start = _real_models.DateField()
        end = _real_models.DateField()

        def clean(self):
            """
            Cross-field validation lives here.
            Single-field validation belongs in the field's validators=[] list instead.

            clean() is called by full_clean(), which is called by:
              - ModelForm.is_valid()  (Django admin uses ModelForms too)
            But NOT called by:
              - obj.save()
              - objects.create()
              - objects.update()
              - objects.bulk_create()
              - DRF ModelSerializer.is_valid()  (serializer does its own validation,
                but does NOT invoke the model's clean())
            """
            if self.end and self.start and self.end <= self.start:
                raise ValidationError({"end": "End date must be after start date."})

        def save(self, *args, **kwargs):
            """
            Optionally call full_clean() in save() to enforce validation on all paths.
            Trade-off: adds validation cost on every write; bulk paths still bypass this.
            For absolute safety, pair with a DB-level CheckConstraint (see Meta below).
            """
            self.full_clean()
            super().save(*args, **kwargs)

        class Meta:
            app_label = "blog"
            constraints = [
                # DB-level guarantee — enforced even by raw SQL, bulk_create, and other services.
                # Django 4.1+ validate_constraints() also checks these inside full_clean().
                _real_models.CheckConstraint(
                    check=_real_models.Q(end__gt=_real_models.F("start")),
                    name="booking_end_after_start",
                ),
            ]

    # Correct usage on non-form paths (scripts, management commands, API services):
    FULL_CLEAN_USAGE = """
    booking = Booking(start=start_date, end=end_date)
    booking.full_clean()   # raises ValidationError with field-level messages
    booking.save()

    # For DRF — model clean() does NOT run automatically; add it explicitly:
    class BookingSerializer(ModelSerializer):
        def validate(self, data):
            instance = Booking(**data)
            try:
                instance.full_clean()
            except ValidationError as exc:
                raise serializers.ValidationError(exc.message_dict)
            return data
    """


VALIDATION_CALL_TABLE = """
Path                                     full_clean() called?
────────────────────────────────────────────────────────────
ModelForm.is_valid()                     YES (only auto path)
Django admin save                        YES (admin uses ModelForm)
obj.save()                               NO  ← classic trap
objects.create()                         NO
objects.update()                         NO
objects.bulk_create()                    NO
DRF ModelSerializer.is_valid()           NO  (serializer's own validation only)
────────────────────────────────────────────────────────────
clean() vs CheckConstraint:
  clean()         → friendly per-field messages, but only when full_clean() is called.
                    Cannot prevent race conditions (check-then-save window).
  CheckConstraint → enforced on every write at DB level; catches race conditions;
                    raises IntegrityError (catch and translate to user-friendly message).
Rule: put the invariant in a DB constraint AND give it a friendly message in clean().
"""


# ==========================================================================
# 5. SIGNALS — dispatch_uid, hidden control flow, bulk-ops gap
# ==========================================================================

SIGNAL_PATTERNS = """
# signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

# ALWAYS use dispatch_uid — prevents duplicate registration if ready() runs twice
# (Django's autoreloader or double-import) which would fire the handler multiple times.
@receiver(post_save, sender='blog.Order', dispatch_uid='order_post_save_create_invoice')
def create_invoice_on_order(sender, instance, created, **kwargs):
    if created:
        from blog.models import Invoice     # local import avoids circular dependency
        Invoice.objects.create(order=instance)

# Register signals in your AppConfig.ready():
#   class BlogConfig(AppConfig):
#       def ready(self):
#           import blog.signals   # noqa: F401

# ── Three problems with signals ───────────────────────────────────────────
# 1. HIDDEN CONTROL FLOW: Order.objects.create() creates an Invoice — nothing in
#    that line of code hints at it. New team members spend hours in 'git grep'.
#
# 2. BULK OPS GAP: pre_save and post_save do NOT fire for:
#      Order.objects.update(...)     — direct SQL UPDATE
#      Order.objects.bulk_create([]) — direct SQL INSERT batch
#      Order.objects.bulk_update()   — direct SQL UPDATE batch
#    Signal-dependent critical logic silently skips bulk paths.
#
# 3. DIFFICULT TO TEST: you must trigger the signal (create the object) to test the
#    handler; you cannot just call the function with arguments.

# ── Modern consensus (HackSoft styleguide, Two Scoops of Django) ──────────
# For communication BETWEEN your own apps: prefer service functions.
# Signals are appropriate ONLY when:
#   a) You need to react to a model you do not own (e.g. auth.User via post_save).
#   b) Reusable/pluggable app that must stay decoupled from caller code.
#   c) Django lifecycle hooks like post_migrate for programmatic data setup.

# ── Service layer alternative ─────────────────────────────────────────────
def place_order(user, items) -> 'Order':
    \"\"\"
    Explicit, testable, debuggable — all side effects visible in one function.
    Works correctly with bulk operations because the service controls every step.
    \"\"\"
    from django.db import transaction
    with transaction.atomic():
        order = Order.objects.create(user=user, subtotal=_calculate_subtotal(items))
        Invoice.objects.create(order=order)
        transaction.on_commit(lambda: send_confirmation_email.delay(order.pk))
    return order
"""


SIGNAL_DECISION_TABLE = """
Situation                                         Recommended approach
──────────────────────────────────────────────────────────────────────────
Derived field on same model (slug, tax)           save() override
React to third-party model (auth.User)            Signal + dispatch_uid
Multi-model business flow in your own code        Service function
Invariant that bulk ops must respect              DB constraint / GeneratedField
Post-migrate setup (initial data, permissions)    post_migrate signal
──────────────────────────────────────────────────────────────────────────
"""


# ==========================================================================
# 6. DJANGO CACHE FRAMEWORK
# ==========================================================================

CACHE_PATTERNS = """
# ── 1. PER-VIEW CACHE (full response caching) ─────────────────────────────
from django.views.decorators.cache import cache_page

@cache_page(60 * 15)    # 15 minutes
def product_list(request):
    ...

# In URLconf (useful when you do not control the view function):
from django.urls import path
urlpatterns = [
    path('products/', cache_page(900)(views.product_list)),
]

# WARNING: cache_page caches per URL + Vary headers.
# NEVER use it for user-specific content — the first user's page is served to all.
# Only GET/HEAD requests with HTTP 200 are cached.
# Each unique query string is a separate cache entry.


# ── 2. LOW-LEVEL CACHE API ────────────────────────────────────────────────
from django.core.cache import cache

cache.set('hot_posts', posts, timeout=300)               # set with TTL (seconds)
posts = cache.get('hot_posts')                           # returns None on miss
posts = cache.get_or_set('hot_posts', compute_hot_posts, 300)  # callable is LAZY

cache.delete('hot_posts')                                # explicit invalidation
cache.incr('page_hits')                                  # atomic increment (Redis / Memcached)

# get_or_set with a callable is preferred: the callable is only invoked on a miss,
# avoiding the "check then compute then set" race condition.


# ── 3. cached_property — instance-level memoisation ──────────────────────
from django.utils.functional import cached_property   # Django's version (no class-level lock)
# from functools import cached_property               # stdlib version

class Report(models.Model):
    @cached_property
    def expensive_total(self):
        return self.lines.aggregate(t=Sum('amount'))['t']

r = Report.objects.get(pk=1)
r.expensive_total   # DB query runs once, result stored in r.__dict__
r.expensive_total   # served from __dict__ — zero queries
del r.expensive_total   # invalidate (works for both Django and stdlib versions)

# Interview answer: Django's cached_property vs functools.cached_property
# In Python 3.8–3.11 functools.cached_property had a class-level threading lock that
# serialised all instances on that property — major performance bug in multi-threaded
# servers. Django's version never had a class-level lock. Python 3.12 removed the lock
# from functools too, so both behave identically on 3.12+. Django internally uses its
# own version; for application code either works on 3.12+.


# ── 4. INVALIDATION PATTERNS ─────────────────────────────────────────────

# Pattern 1: write-through delete (simple but error-prone across multiple write paths)
def save(self, *args, **kwargs):
    super().save(*args, **kwargs)
    cache.delete(f'product:{self.pk}')

# Pattern 2: version key — invalidate a whole group with a single incr
v = cache.get_or_set('products:version', 1, None)   # no TTL on the version key
cache.set(f'products:v{v}:list:page1', data, 600)
# Invalidate all product caches at once — old keys orphan and expire naturally:
cache.incr('products:version')

# Pattern 3: Django's built-in version parameter
cache.set('list', data, version=2)
cache.get('list', version=2)    # version mismatch → cache miss

# Pattern 4: TTL-only (simplest) — accept up to N seconds of stale data.
# Use when eventual consistency is acceptable; no invalidation code needed at all.
"""


# ==========================================================================
# 7. TestCase vs TransactionTestCase — on_commit, setUpTestData
# ==========================================================================

TESTING_PATTERNS = """
# ── Core difference ───────────────────────────────────────────────────────
from django.test import TestCase, TransactionTestCase

# TestCase: wraps each test in an atomic block, ROLLS BACK at the end.
# - Fast: rollback is orders of magnitude cheaper than truncating tables.
# - The database never sees a real COMMIT inside the test.
# - Use for 95%+ of your tests.

# TransactionTestCase: allows real COMMIT; truncates all tables after each test.
# - Slow.
# - Required for: testing transaction behaviour, on_commit hooks, concurrency.


# ── on_commit inside TestCase — the classic pitfall ──────────────────────
# Production code:
def place_order(user, items):
    order = Order.objects.create(...)
    transaction.on_commit(lambda: send_confirmation_email.delay(order.pk))

# Bad test (callback never fires — TestCase never commits):
class OrderBadTest(TestCase):
    def test_email_queued(self):
        place_order(self.user, self.items)
        # send_confirmation_email.delay was NEVER called — on_commit pending forever

# Correct fix — Django 3.2+:
class OrderGoodTest(TestCase):
    def test_email_queued(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            place_order(self.user, self.items)
        # callbacks list holds every on_commit callable that would have run
        self.assertEqual(len(callbacks), 1)
        # execute=True means they were also actually called — Celery task was enqueued

# captureOnCommitCallbacks gives you TestCase speed + on_commit coverage.
# TransactionTestCase alternative works but is significantly slower.


# ── setUpTestData vs setUp ────────────────────────────────────────────────
class PostTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Runs ONCE per test CLASS — data is created inside a class-level atomic block.
        # After each test the DB is rolled back to this state (not re-created).
        # Use for read-only fixtures that many tests share — massive speed gain.
        # e.g. 50 posts × 20 tests: 50 INSERTs instead of 1000.
        cls.author = User.objects.create_user('ashish', password='secret')
        cls.posts = [Post.objects.create(author=cls.author, title=f'Post {i}')
                     for i in range(50)]

    def setUp(self):
        # Runs before EACH test — only for state that individual tests MUTATE.
        # Avoid creating DB objects here if setUpTestData covers it.
        self.client.force_login(self.author)

    # Pitfall: Django 3.2+ deep-copies setUpTestData class attributes for each test
    # to prevent in-memory state leaking between tests. DB mutations are rolled back.
    # But if you do cls.author.username = 'changed' in a test, the next test gets
    # a fresh copy — safe. If you mutate a mutable child list on cls.posts, be aware.


# ── pytest-django equivalents ─────────────────────────────────────────────
import pytest

@pytest.mark.django_db                  # atomic + rollback — equivalent to TestCase
def test_create_post(db):
    ...

@pytest.mark.django_db(transaction=True)  # real commits — equivalent to TransactionTestCase
def test_on_commit(db):
    ...

@pytest.fixture
def author(db):                         # 'db' fixture implicitly provides django_db mark
    return User.objects.create_user('ashish')
"""


# ==========================================================================
# 8. AUTH INTERNALS — authenticate(), login(), logout()
# ==========================================================================

AUTH_INTERNALS = """
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect


def login_view(request):
    username = request.POST.get('username')
    password = request.POST.get('password')

    # authenticate() iterates AUTHENTICATION_BACKENDS in order.
    # Each backend's .authenticate(request, **credentials) is called.
    # First non-None return wins; PermissionDenied halts the chain immediately.
    # Default ModelBackend: fetch by username → check_password() → is_active check.
    # Subtle: even when the user is NOT found, the hasher runs once to prevent
    # timing attacks that would let an attacker enumerate valid usernames.
    user = authenticate(request, username=username, password=password)

    if user is not None:
        # login() does three important things:
        # 1. Writes _auth_user_id, _auth_user_backend, _auth_user_hash to the session.
        #    _auth_user_hash = HMAC of the password hash — changing the password
        #    immediately invalidates ALL other sessions (no manual logout needed).
        # 2. Calls session.cycle_key() — generates a NEW session key while preserving
        #    session data.  This prevents SESSION FIXATION ATTACKS where an attacker
        #    pre-seeds a known session ID, waits for the victim to log in, then reuses
        #    that same ID to access the now-authenticated session.
        # 3. Fires the user_logged_in signal.
        login(request, user)
        return redirect('home')

    # Authentication failed — show error, do NOT reveal whether username or password
    # was wrong (information leakage).
    ...


def logout_view(request):
    # logout() calls request.session.flush():
    # - Deletes the session data from the DB/store.
    # - Deletes the session cookie value.
    # - Generates a fresh empty session with a new key.
    # Simply setting request.user = AnonymousUser() would NOT secure the session —
    # the old session key would still be valid and reusable.
    logout(request)
    return redirect('login')


# ── View protection — FBV vs CBV ─────────────────────────────────────────
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

@login_required                         # anonymous → redirect to settings.LOGIN_URL?next=/path/
def dashboard(request):
    ...

class DashboardView(LoginRequiredMixin, TemplateView):
    # LoginRequiredMixin MUST be leftmost in the MRO (before TemplateView / View)
    # so its dispatch() runs first and can redirect before the view logic.
    template_name = 'dashboard.html'
    login_url = '/accounts/login/'      # override per-view
    # raise_exception = True            # → 403 Forbidden instead of redirect

# @login_required on a CLASS does not work — it is a function decorator.
# For CBVs use: @method_decorator(login_required, name='dispatch')
"""


# ==========================================================================
# 9. DEPLOYMENT — WhiteNoise + DEBUG=False checklist
# ==========================================================================

DEPLOYMENT_SETTINGS = """
# settings/production.py

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Core safety settings ──────────────────────────────────────────────────
DEBUG = False
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']   # Missing env var → crash at startup (correct)

# Empty ALLOWED_HOSTS with DEBUG=False causes every request to return 400 Bad Request.
# Django's Host header validation triggers to prevent HTTP host-header injection.
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'api.mysite.com').split(',')

CSRF_TRUSTED_ORIGINS = ['https://mysite.com']  # Required for cross-origin POST (Django 4+)

# ── WhiteNoise — serve static files directly from Django/WSGI ────────────
# pip install whitenoise
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # IMMEDIATELY after Security, before everything else
    # ... other middleware
]

STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {                                       # Django 4.2+ syntax
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        # CompressedManifestStaticFilesStorage:
        #   - Adds content hash to filenames (style.a1b2c3.css) → automatic cache busting
        #   - Pre-generates gzip and brotli compressed versions
        #   - Sets far-future Cache-Control headers (1 year) on hashed files
    },
}
# Deploy step: python manage.py collectstatic --noinput

# WHY WhiteNoise: DEBUG=False makes Django's runserver stop serving static files.
# Without WhiteNoise (or nginx/CDN in front), all CSS/JS returns 404.
# WhiteNoise handles small/medium apps on Heroku, Railway, Render without nginx config.

# ── HTTPS / HSTS / cookie security ───────────────────────────────────────
SECURE_SSL_REDIRECT = True                  # http:// → https:// permanent redirect
SECURE_HSTS_SECONDS = 31536000              # 1 year; start with 300 and increase gradually
SECURE_HSTS_INCLUDE_SUBDOMAINS = True       # apply HSTS to all subdomains
SECURE_HSTS_PRELOAD = True                  # eligible for browser preload lists
SESSION_COOKIE_SECURE = True                # session cookie: HTTPS only
CSRF_COOKIE_SECURE = True                   # CSRF cookie: HTTPS only
SECURE_BROWSER_XSS_FILTER = True           # X-XSS-Protection header
X_FRAME_OPTIONS = 'DENY'                    # Clickjacking protection

# Run this to audit every setting:  python manage.py check --deploy
"""


DEPLOYMENT_CHECKLIST = """
Item                                 If forgotten → this happens
─────────────────────────────────────────────────────────────────────────────
ALLOWED_HOSTS configured             Every request returns 400 Bad Request
collectstatic + WhiteNoise/nginx     All CSS/JS returns 404 (DEBUG=False stops serving)
templates/404.html, 500.html         Users see plain-text/blank error pages
SECURE_* settings configured         Cookies transmit over HTTP; no HSTS; XSS risk
SECRET_KEY from environment          Hardcoded secret in version control — critical vuln
Error tracking (Sentry, etc.)        500 errors are silent; you learn from user reports
CSRF_TRUSTED_ORIGINS set             Cross-origin form POSTs fail with 403
─────────────────────────────────────────────────────────────────────────────
Verification command: python manage.py check --deploy
This command audits all SECURE_* and DEBUG/ALLOWED_HOSTS settings and prints
actionable warnings for every missing or insecure configuration.
"""


# ==========================================================================
# 10. INTERVIEW Q&A REFERENCE
# ==========================================================================

INTERVIEW_ANSWERS = {
    "Q1_middleware_hooks_order": (
        "5 hooks and their order: "
        "(1) __init__ — once at server start. "
        "(2) __call__ pre-get_response — request phase, top-down through MIDDLEWARE list. "
        "(3) process_view — after URL resolution, before view, top-down. "
        "(4) process_exception — after uncaught view exception, bottom-up (reverse list order). "
        "(5) process_template_response — for TemplateResponse before render, bottom-up. "
        "(6) __call__ post-get_response — response phase, bottom-up. "
        "Mental model: onion — request inward, response outward."
    ),

    "Q2_sentry_hook": (
        "Sentry uses process_exception. Uncaught view exceptions propagate bottom-up "
        "through the middleware chain. Sentry's middleware captures the exception with "
        "full stack context, then returns None so Django's normal 500 handling continues. "
        "Zero view-code changes needed."
    ),

    "Q3_short_circuit": (
        "When middleware B returns an HttpResponse without calling get_response(), "
        "all middleware below B (C, D...) and the view are skipped. "
        "However, all middleware ABOVE B (A) that already passed their request phase "
        "will still run their response phase — the response exits through the outer "
        "layers of the onion. SecurityMiddleware is first in MIDDLEWARE so its response "
        "phase runs on every response, even short-circuited ones."
    ),

    "Q4_get_exceptions": (
        "get() raises Model.DoesNotExist (0 rows) or Model.MultipleObjectsReturned (2+ rows). "
        "Handle DoesNotExist with try/except or get_object_or_404 (views) or .first() (None semantics). "
        "MultipleObjectsReturned signals a missing uniqueness constraint — handle it AND add the constraint. "
        "Prefer model-specific exceptions (User.DoesNotExist) over generic ObjectDoesNotExist to "
        "avoid silently swallowing exceptions from other models in nested queries."
    ),

    "Q5_union_filter": (
        "SQL UNION produces a combined opaque result set. Django only supports order_by() "
        "and slicing (LIMIT/OFFSET) on a union result. filter() and annotate() raise "
        "NotSupportedError. Solution: apply all filters BEFORE union(). "
        "For same-model OR with further filtering, use Q(a) | Q(b) instead of union — "
        "it stays a composable queryset. Union is correct only for different models "
        "or when both branches are already fully filtered/annotated."
    ),

    "Q6_migration_conflict": (
        "Two migrations with the same parent create two leaf nodes in the migration "
        "graph — Django raises 'Conflicting migrations detected'. "
        "Fix 1: makemigrations --merge creates an empty merge migration pointing to both leaves. "
        "Safe only if the two migrations touch different fields/tables. "
        "Fix 2 (cleaner): delete your unapplied migration and re-run makemigrations — "
        "it now creates a new migration on top of the teammate's. "
        "Prevention: always pull/rebase from main before running makemigrations; "
        "add makemigrations --check --dry-run to CI."
    ),

    "Q7_save_override_bug": (
        "update(), bulk_create(), and bulk_update() execute direct SQL — they bypass "
        "Python-level save() and all signals. Also: if save(update_fields=['status']) is called "
        "and your override modifies 'tax' but does not add 'tax' to update_fields, "
        "the change is silently dropped. For invariants that must survive all write paths, "
        "enforce them at the DB level (GeneratedField, CheckConstraint, trigger)."
    ),

    "Q8_clean_not_called": (
        "save() NEVER calls full_clean(). The only automatic invocation is ModelForm.is_valid() "
        "(which includes Django admin). objects.create(), objects.update(), bulk_create(), and "
        "DRF ModelSerializer.is_valid() all skip the model's clean(). "
        "Fix: call full_clean() explicitly on non-form paths; pair with a DB-level "
        "CheckConstraint for race-condition safety."
    ),

    "Q9_on_commit_testcase": (
        "TestCase wraps each test in an atomic block and ROLLS BACK at the end — "
        "no COMMIT ever occurs, so on_commit callbacks remain pending forever. "
        "Fix: use captureOnCommitCallbacks(execute=True) context manager (Django 3.2+) — "
        "captures and executes the callbacks within the TestCase, preserving speed. "
        "Alternative: use TransactionTestCase or pytest.mark.django_db(transaction=True), "
        "but these are much slower because they truncate tables after each test."
    ),

    "Q10_login_session_rotation": (
        "login() calls session.cycle_key() to generate a new session key after authentication. "
        "This prevents session fixation attacks: an attacker pre-seeds a known session ID "
        "(via URL or cookie injection); if the ID were unchanged after login the attacker "
        "could reuse it to access the authenticated session. Rotation makes the pre-seeded "
        "ID useless. login() also stores _auth_user_hash (HMAC of the password hash) so "
        "that a password change immediately invalidates all other sessions. "
        "logout() calls session.flush() — deletes session data, the DB row, and issues "
        "a new empty session key; it does not merely set user = AnonymousUser."
    ),
}
