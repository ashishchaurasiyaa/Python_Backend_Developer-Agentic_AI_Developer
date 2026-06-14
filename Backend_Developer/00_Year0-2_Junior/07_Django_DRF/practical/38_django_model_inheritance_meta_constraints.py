"""
Django Model Inheritance & Meta Constraints — Production Patterns
=================================================================
Covers all three inheritance flavours (Abstract, Multi-Table, Proxy) plus
Meta.indexes (composite, partial, functional) and Meta.constraints
(UniqueConstraint, CheckConstraint) with the race-condition story.

Reference: 38_django_model_inheritance_meta_constraints.md

Setup (Django project, not a standalone script):
    # pip install django djangorestframework psycopg2-binary django-polymorphic

This module is structured as importable production code — it defines the
models and utilities exactly as they would appear in a real Django app.
Django must be configured (DJANGO_SETTINGS_MODULE) before importing.
Run the __main__ demo block for a configuration-free structural walkthrough.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

# ---------------------------------------------------------------------------
# Django imports — fine to import even without a running project for py_compile.
# The module-level django.setup() call in __main__ wires everything up.
# ---------------------------------------------------------------------------
import django
from django.conf import settings
from django.db import IntegrityError, models
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.utils import timezone

if TYPE_CHECKING:
    pass


# ==========================================================================
# 0. DJANGO SETTINGS — inline minimal config so this file is self-contained
#    when run directly.  In a real project, remove this block.
# ==========================================================================

def _configure_django() -> None:
    """Configure Django with an in-memory SQLite database for the demo."""
    if settings.configured:
        return
    settings.configure(
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            # Our "app" is this module itself — no app label needed for the demo.
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
        USE_TZ=True,
    )
    django.setup()


# ==========================================================================
# 1. ABSTRACT BASE CLASSES — zero JOINs, fields copied into each child table
# ==========================================================================

class TimeStampedModel(models.Model):
    """
    Reusable audit timestamps.  Inherit instead of copy-pasting two fields
    into every model.  No database table is created for this class.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True          # ← the magic: no table, no migrations for this class


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet that routes .delete() to a flag-set rather than a hard DELETE."""

    def delete(self):
        """Bulk soft-delete — covers qs.delete() as well as single-instance."""
        return super().update(deleted_at=timezone.now())

    def alive(self):
        """Return only rows that have not been soft-deleted."""
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        """Return only soft-deleted rows (useful for admin/recovery views)."""
        return self.filter(deleted_at__isnull=False)


class SoftDeleteModel(models.Model):
    """
    Soft-delete mixin.  Rows are flagged with a timestamp instead of being
    physically removed — supports audit trails and recovery workflows.

    .delete()      → sets deleted_at, row stays
    .hard_delete() → calls real SQL DELETE when you truly need it
    """

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=False)

    objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):  # type: ignore[override]
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def hard_delete(self):
        """Permanently remove the row from the database."""
        super().delete()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Composing multiple abstract bases — all fields land in ONE table.
# ---------------------------------------------------------------------------

class Article(TimeStampedModel, SoftDeleteModel):
    """
    Resulting table columns: id, title, body, created_at, updated_at, deleted_at.
    Single-table — no JOIN, single INSERT, single UPDATE.
    """

    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]   # child can override parent Meta freely


# ---------------------------------------------------------------------------
# ForeignKey inside an abstract base — MUST use %(class)s placeholder.
# ---------------------------------------------------------------------------

class Ownable(models.Model):
    """
    Abstract mixin that adds an owner FK.
    related_name uses placeholders so each concrete child gets a unique
    reverse accessor — avoids fields.E305 clash at makemigrations time.

    Document  → user.blog_document_set
    Invoice   → user.blog_invoice_set
    """

    owner = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",   # ← required for abstract FK
    )

    class Meta:
        abstract = True


class Document(Ownable):
    title = models.CharField(max_length=255)


class Invoice(Ownable):
    total = models.DecimalField(max_digits=10, decimal_places=2)


# ==========================================================================
# 2. MULTI-TABLE INHERITANCE (MTI) — parent + child each have their own table
#    Django auto-creates an implicit OneToOneField (place_ptr) as child PK.
# ==========================================================================

class Place(models.Model):
    """Concrete parent — always gets its own table."""

    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)

    def __str__(self) -> str:
        return self.name


class Restaurant(Place):
    """
    MTI child.  Django implicitly adds:
        place_ptr = OneToOneField(Place, parent_link=True,
                                  primary_key=True, on_delete=CASCADE)

    SQL generated:
        SELECT * FROM restaurant
        INNER JOIN place ON restaurant.place_ptr_id = place.id
        WHERE serves_pizza = true;

    Every fetch, every save touches TWO tables — the JOIN tax.
    Only choose MTI when Place rows need to be independently queryable
    (e.g. a calendar that lists all Event subtypes via FK to Event).
    """

    serves_pizza = models.BooleanField(default=False)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0)


# Polymorphic query problem illustrated as a docstring — runtime would need
# django-polymorphic to solve it without extra queries per row.
_MTI_POLYMORPHISM_NOTE = """
places = Place.objects.all()   # includes Restaurants, but returns Place instances
for p in places:
    # p.serves_pizza       → AttributeError: 'Place' object has no attribute 'serves_pizza'
    # p.restaurant         → extra query + DoesNotExist if it is not a Restaurant
    pass

# Fix: django-polymorphic (PolymorphicModel base) — automatic downcast via
# content_type tracking.  Still uses JOINs; no free lunch.
# pip install django-polymorphic
"""


# ==========================================================================
# 3. PROXY MODELS — same table, different Python-level behaviour
# ==========================================================================

class Order(models.Model):
    """Base order model — full table backing every proxy variant."""

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self) -> str:
        return f"Order #{self.pk} [{self.status}]"


class PendingOrderManager(models.Manager):
    """Default queryset pre-filtered to pending orders only."""

    def get_queryset(self):
        return super().get_queryset().filter(status=Order.STATUS_PENDING)


class PendingOrder(Order):
    """
    Proxy model: no new table, no new columns.
    Adds a role-specific manager and FIFO ordering for a support-team queue.

    Admin trick: register both Order (full view) and PendingOrder (queue view)
    in admin.py — two sidebar entries, same underlying data, zero duplication.
    """

    objects = PendingOrderManager()  # type: ignore[assignment]

    class Meta:
        proxy = True
        ordering = ["created_at"]    # FIFO queue semantics

    def approve(self) -> None:
        """Transition this order from pending to approved."""
        self.status = Order.STATUS_APPROVED
        self.save(update_fields=["status"])

    def cancel(self) -> None:
        """Transition this order from pending to cancelled."""
        self.status = Order.STATUS_CANCELLED
        self.save(update_fields=["status"])


# Proxy limitation — illustrated in a docstring:
_PROXY_FIELD_ERROR = """
class PendingOrder(Order):
    priority = models.IntegerField()   # ❌ FieldError at runtime
    class Meta:
        proxy = True
# Proxy shares the underlying table — no new column can be added.
# Need new fields? Use an abstract base or an explicit OneToOne instead.
"""


# ==========================================================================
# 4. META.INDEXES — composite, descending, partial, functional
# ==========================================================================

class Subscription(models.Model):
    """
    Illustrates composite + partial index patterns on a soft-deletable model.

    Left-prefix rule recap:
        Index(fields=['user', 'plan']) is like a phone book sorted first by
        user, then by plan within each user.

        filter(user=u)              ✅ uses index (left prefix present)
        filter(user=u, plan='pro')  ✅ full index
        filter(plan='pro')          ❌ index unused — left column missing
    """

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    plan = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    starts_at = models.DateTimeField()

    class Meta:
        indexes = [
            # ----------------------------------------------------------------
            # 4a. Composite index — equality filter on user (high selectivity
            #     column first), range/equality on plan.
            # ----------------------------------------------------------------
            models.Index(
                fields=["user", "plan"],
                name="sub_user_plan_idx",
            ),

            # ----------------------------------------------------------------
            # 4b. Partial index — covers only active (non-deleted) rows.
            #     Table may have 80 % soft-deleted junk; this index stays
            #     small, fits in RAM, and maintenance cost on writes is lower.
            #     Query MUST include the matching condition for the planner to
            #     choose this index:
            #         filter(user=u, deleted_at__isnull=True)  ✅
            #         filter(user=u)                           ❌
            #     Postgres / SQLite only — MySQL does not support partial indexes.
            # ----------------------------------------------------------------
            models.Index(
                fields=["user"],
                name="sub_active_user_idx",
                condition=Q(deleted_at__isnull=True),
            ),

            # ----------------------------------------------------------------
            # 4c. Descending index — "latest subscriptions first" dashboard
            #     queries benefit from a DESC index that matches ORDER BY direction.
            # ----------------------------------------------------------------
            models.Index(
                fields=["-starts_at"],
                name="sub_starts_at_desc_idx",
            ),
        ]


class UserProfile(models.Model):
    """
    Illustrates functional (expression) index for case-insensitive lookups.

    Without the functional index, filter(email__iexact=...) causes a full
    table scan because the plain email column index does not cover LOWER().
    """

    email = models.EmailField(unique=False)   # uniqueness handled via constraint below
    username = models.CharField(max_length=150)

    class Meta:
        indexes = [
            # ----------------------------------------------------------------
            # 4d. Functional index — LOWER(email) so iexact login lookups are
            #     fast without a full table scan.
            #     filter(email__iexact='User@Example.com') → hits this index.
            # ----------------------------------------------------------------
            models.Index(Lower("email"), name="userprofile_email_lower_idx"),
            models.Index(Lower("username"), name="userprofile_username_lower_idx"),
        ]
        constraints = [
            # Case-insensitive unique email (constraint + index together)
            models.UniqueConstraint(Lower("email"), name="uniq_userprofile_email_ci"),
            models.UniqueConstraint(Lower("username"), name="uniq_userprofile_username_ci"),
        ]


# ==========================================================================
# 5. META.CONSTRAINTS — UniqueConstraint (replaces unique_together) +
#    CheckConstraint (DB-enforced business rules)
# ==========================================================================

class Student(models.Model):
    name = models.CharField(max_length=100)


class Course(models.Model):
    title = models.CharField(max_length=200)


class Enrollment(models.Model):
    """
    Demonstrates the full UniqueConstraint feature set that unique_together
    could not provide:

    1. Plain composite unique
    2. Partial unique   — only active enrollments unique; historical
                          (is_active=False) rows can repeat the same pair.
    3. nulls_distinct   — Django 5.0+, Postgres 15+ feature.

    unique_together is on the deprecated path in Django docs — new code
    should always use Meta.constraints with UniqueConstraint.
    """

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    email_backup = models.EmailField(null=True, blank=True)

    class Meta:
        # ❌ OLD (do not use in new code):
        # unique_together = [('student', 'course')]

        constraints = [
            # ------------------------------------------------------------------
            # 5a. Plain composite unique — one active or inactive record per pair.
            #     Use this when you simply need uniqueness regardless of other cols.
            # ------------------------------------------------------------------
            models.UniqueConstraint(
                fields=["student", "course"],
                name="uniq_student_course",
            ),

            # ------------------------------------------------------------------
            # 5b. Partial unique — uniqueness only among active enrollments.
            #     A student who drops (is_active=False) can re-enroll later;
            #     the history of inactive rows is allowed to duplicate.
            #     This was impossible with unique_together.
            # ------------------------------------------------------------------
            # NOTE: Constraint 5a above already covers the full pair, so 5b
            # is shown here for illustration only.  In a real schema you would
            # choose one or the other depending on business rules.
            # models.UniqueConstraint(
            #     fields=["student", "course"],
            #     condition=Q(is_active=True),
            #     name="uniq_active_enrollment",
            # ),

            # ------------------------------------------------------------------
            # 5c. nulls_distinct=False (Django 5.0+, Postgres 15+):
            #     Default SQL behaviour: NULL != NULL → multiple NULL emails OK.
            #     nulls_distinct=False → only ONE NULL email_backup row allowed.
            # ------------------------------------------------------------------
            models.UniqueConstraint(
                fields=["email_backup"],
                nulls_distinct=False,
                name="uniq_enrollment_email_backup_one_null",
            ),
        ]


class Payment(models.Model):
    """
    CheckConstraints demonstrate DB-enforced business rules that survive
    every access path: ORM, bulk_create, raw SQL, migrations, other services
    sharing the same database.  App-level validators only catch requests
    that flow through Django's form/serializer layer.
    """

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    idempotency_key = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=[("pending", "Pending"), ("success", "Success"), ("failed", "Failed")],
        default="pending",
    )

    class Meta:
        constraints = [
            # ------------------------------------------------------------------
            # 5d. amount must be positive — catches bad inserts at the DB level.
            #     Payment.objects.create(amount=-50) → IntegrityError immediately.
            # ------------------------------------------------------------------
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="payment_amount_positive",
            ),

            # ------------------------------------------------------------------
            # 5e. Cross-column check — discount cannot exceed the full amount.
            #     F() references a column on the same row.
            # ------------------------------------------------------------------
            models.CheckConstraint(
                condition=Q(discount__lte=F("amount")),
                name="payment_discount_not_more_than_amount",
            ),

            # ------------------------------------------------------------------
            # 5f. Temporal integrity — end must come after start.
            # ------------------------------------------------------------------
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")),
                name="payment_ends_after_starts",
            ),

            # ------------------------------------------------------------------
            # 5g. Partial unique on idempotency_key — retry-safe payment API.
            #     Two requests with the same key cannot both be pending/success.
            #     Failed payments are excluded so a retry gets a new attempt.
            #     Gateway webhook duplicate → second INSERT → IntegrityError →
            #     caller catches and returns the existing payment — zero double-charge.
            # ------------------------------------------------------------------
            models.UniqueConstraint(
                fields=["idempotency_key"],
                condition=Q(status__in=["pending", "success"]),
                name="uniq_active_idempotency_key",
            ),
        ]


# ==========================================================================
# 6. SAAS BASE MODEL — composition pattern used in real multi-tenant services
# ==========================================================================

class BaseModel(TimeStampedModel, SoftDeleteModel):
    """
    Composite abstract base used across all tenant-facing models in a SaaS app:
    - UUID primary key    → no sequential ID leakage, safe to expose in URLs
    - created_at          → from TimeStampedModel
    - updated_at          → from TimeStampedModel
    - deleted_at          → from SoftDeleteModel (soft-delete + SoftDeleteQuerySet)

    All fields land in ONE table per concrete child — no JOINs, no surprises.

    Usage:
        class Workspace(BaseModel):
            name = models.CharField(max_length=255)
            # Table: id (UUID), name, created_at, updated_at, deleted_at
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class Workspace(BaseModel):
    """Example concrete SaaS model — inherits all BaseModel fields."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("slug"), name="uniq_workspace_slug_ci"),
        ]

    def __str__(self) -> str:
        return self.name


# ==========================================================================
# 7. RACE CONDITION DEMO — why validators are not enough
# ==========================================================================

def register_user_safe(email: str) -> "models.Model":
    """
    Correct pattern for email uniqueness:

    1. Validator (form/serializer layer) gives the user an early, friendly
       error — good UX.
    2. DB UniqueConstraint is the real guard — atomic at INSERT time, closes
       the check-then-act race window that validators cannot close.
    3. Catch IntegrityError and map it back to a user-facing error using the
       constraint NAME (another reason descriptive names matter).

    Race condition scenario (why validators alone fail):
        t=0ms  Request A: SELECT ... WHERE email='x@y.com'  → not found → pass
        t=2ms  Request B: SELECT ... WHERE email='x@y.com'  → not found → pass
        t=5ms  Request A: INSERT ... OK
        t=7ms  Request B: INSERT ... ← IntegrityError — DB catches what the
                          validator could not because A had not committed yet.
    """
    from django.core.exceptions import ValidationError  # local import — Django must be set up

    # In a real User model this would be:
    #   User.objects.create_user(email=email, ...)
    # Here we use UserProfile as our demo model.
    try:
        return UserProfile.objects.create(email=email, username=email.split("@")[0])
    except IntegrityError as exc:
        exc_str = str(exc).lower()
        if "uniq_userprofile_email_ci" in exc_str:
            raise ValidationError({"email": "This email address is already registered."}) from exc
        # Unknown constraint — do not swallow; let it propagate.
        raise


# ==========================================================================
# 8. CONCURRENT INDEX MIGRATION NOTE
# ==========================================================================

_CONCURRENT_INDEX_MIGRATION = """
# Normal AddIndex on a 50 M row Postgres table → write lock → minutes of
# blocked INSERTs/UPDATEs → production outage.

# Fix — create migrations manually or via squash:

from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False          # REQUIRED — CONCURRENTLY cannot run inside a transaction block

    dependencies = [("shop", "0042_previous")]

    operations = [
        AddIndexConcurrently(
            model_name="order",
            index=models.Index(
                fields=["user", "status"],
                name="order_user_status_idx",
            ),
        ),
    ]

# Notes:
# - atomic = False is mandatory; omitting it raises:
#     "CREATE INDEX CONCURRENTLY cannot run inside a transaction block"
# - Concurrently is slower and can leave an INVALID index on failure —
#   check with: SELECT * FROM pg_indexes WHERE indexname = 'order_user_status_idx';
#   Manual cleanup: DROP INDEX CONCURRENTLY order_user_status_idx;
# - For constraints on large tables: NOT VALID + VALIDATE CONSTRAINT two-step
#   (raw SQL migration in zero_downtime_migrations — file 25).
# - RemoveIndexConcurrently is also available for zero-downtime index drops.
"""


# ==========================================================================
# 9. QUICK REFERENCE — 3-Way Inheritance Comparison
# ==========================================================================

INHERITANCE_COMPARISON = {
    "Abstract Base (abstract=True)": {
        "parent_table": False,
        "child_table": True,
        "new_fields_in_child": True,
        "query_cost": "Best — single table, no JOIN",
        "save_cost": "1 SQL statement",
        "parent_queryable": False,
        "fk_to_parent": False,
        "use_case": "Shared fields/behaviour (timestamps, soft-delete, UUID PK)",
    },
    "Multi-Table Inheritance (MTI)": {
        "parent_table": True,
        "child_table": True,
        "new_fields_in_child": True,
        "query_cost": "INNER JOIN on every query — watch EXPLAIN",
        "save_cost": "2 SQL statements (parent + child tables)",
        "parent_queryable": True,
        "fk_to_parent": True,
        "use_case": "Parent rows independently needed (rare) — consider explicit OneToOne first",
    },
    "Proxy (proxy=True)": {
        "parent_table": True,  # shared — same table
        "child_table": False,
        "new_fields_in_child": False,
        "query_cost": "Same as parent — same table",
        "save_cost": "1 SQL statement",
        "parent_queryable": True,
        "fk_to_parent": True,   # FK points to the shared table
        "use_case": "Same data, different behaviour: filtered managers, admin views, role methods",
    },
}


# ==========================================================================
# 10. __main__ DEMO — structural walkthrough without a running DB
# ==========================================================================

if __name__ == "__main__":
    print("=" * 68)
    print("Django Model Inheritance & Meta Constraints — Structure Demo")
    print("=" * 68)

    # ------------------------------------------------------------------
    # 10a. Verify abstract inheritance — check field names on child class
    # ------------------------------------------------------------------
    print("\n[1] Abstract inheritance — Article field names:")
    article_fields = [f.name for f in Article._meta.get_fields()]
    print(f"    {article_fields}")
    assert "created_at" in article_fields, "created_at missing from Article"
    assert "updated_at" in article_fields, "updated_at missing from Article"
    assert "deleted_at" in article_fields, "deleted_at missing from Article"
    assert "title" in article_fields
    print("    All expected fields inherited correctly.")

    # ------------------------------------------------------------------
    # 10b. Proxy model check — same table as parent
    # ------------------------------------------------------------------
    print("\n[2] Proxy model — PendingOrder uses Order's table:")
    assert PendingOrder._meta.proxy is True
    assert PendingOrder._meta.db_table == Order._meta.db_table
    print(f"    PendingOrder.proxy = {PendingOrder._meta.proxy}")
    print(f"    Shared db_table   = '{PendingOrder._meta.db_table}'")

    # ------------------------------------------------------------------
    # 10c. MTI check — Restaurant has place_ptr OneToOneField
    # ------------------------------------------------------------------
    print("\n[3] MTI — Restaurant has a parent link to Place:")
    parent_link = Restaurant._meta.parents.get(Place)
    assert parent_link is not None, "No parent link found"
    print(f"    Parent link field : {parent_link}")

    # ------------------------------------------------------------------
    # 10d. Index definitions on Subscription
    # ------------------------------------------------------------------
    print("\n[4] Subscription Meta.indexes:")
    for idx in Subscription._meta.indexes:
        cond = getattr(idx, "condition", None)
        print(f"    name={idx.name!r:40s}  condition={cond}")

    # ------------------------------------------------------------------
    # 10e. Constraint definitions on Payment
    # ------------------------------------------------------------------
    print("\n[5] Payment Meta.constraints:")
    for con in Payment._meta.constraints:
        print(f"    name={con.name!r}")

    # ------------------------------------------------------------------
    # 10f. Inheritance comparison table
    # ------------------------------------------------------------------
    print("\n[6] 3-Way Inheritance Summary:")
    for kind, props in INHERITANCE_COMPARISON.items():
        print(f"\n  {kind}")
        for k, v in props.items():
            print(f"    {k:<30s}: {v}")

    # ------------------------------------------------------------------
    # 10g. BaseModel (SaaS) UUID PK
    # ------------------------------------------------------------------
    print("\n[7] SaaS BaseModel — Workspace PK field:")
    pk_field = Workspace._meta.pk
    print(f"    PK field type : {type(pk_field).__name__}")
    assert type(pk_field).__name__ == "UUIDField"
    print("    UUID primary key confirmed.")

    print("\n" + "=" * 68)
    print("All structural assertions passed.")
    print("=" * 68)
    print("""
Next steps in a real Django project:
  1. python manage.py makemigrations
  2. python manage.py migrate
  3. Use EXPLAIN ANALYZE in psql to verify index usage.
  4. For large Postgres tables, use AddIndexConcurrently (see section 8).
  5. Register both Order and PendingOrder in admin.py for role-based views.
""")
