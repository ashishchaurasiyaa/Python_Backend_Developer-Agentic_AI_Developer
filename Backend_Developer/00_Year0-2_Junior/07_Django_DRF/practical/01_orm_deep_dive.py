"""
Django ORM Deep Dive — select_related, prefetch_related, annotate, aggregate,
Custom Managers, Performance Tips, and Signals

This module is structured as importable, illustrative code that mirrors
production patterns used in real Django projects.  It does NOT require a
running database — all model definitions and usage examples are written so
that py_compile (syntax check) passes cleanly, and the logic can be dropped
straight into a Django project.

Topics covered (grounded in 01_orm_deep_dive.md):
  1. Model definitions — Author / Book / Tag / Order / Product / User
  2. Solving the N+1 problem — select_related & prefetch_related
  3. Aggregate vs Annotate — Count, Sum, Avg, Max, Min
  4. F expressions — column-level arithmetic without loading into Python
  5. Q objects — complex OR / AND / NOT filter compositions
  6. Custom QuerySets and Managers — chainable, reusable business logic
  7. ORM performance toolkit — only(), defer(), values(), iterator(),
     exists(), bulk_create(), bulk_update(), select_for_update()
  8. Django Signals — post_save, pre_save, post_delete, and custom signals

External dependencies (pip install django):
  pip install django
"""

# pip install django

from __future__ import annotations

import logging
from decimal import Decimal
from functools import wraps
from typing import List, Optional

from django.db import models, transaction
from django.db.models import (
    Avg,
    Count,
    F,
    Max,
    Min,
    Q,
    Sum,
)
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import Signal, receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


# ==========================================================================
# 1. MODEL DEFINITIONS
# ==========================================================================

class Tag(models.Model):
    """A label that can be attached to many books (ManyToMany side)."""

    name: str = models.CharField(max_length=50)

    class Meta:
        app_label = "library"

    def __str__(self) -> str:
        return self.name


class Author(models.Model):
    """Represents a book author — the 'one' side of a ForeignKey."""

    name: str = models.CharField(max_length=100)
    email: str = models.EmailField(unique=True)

    class Meta:
        app_label = "library"

    def __str__(self) -> str:
        return self.name


class Book(models.Model):
    """
    Central model:
      - ForeignKey  → Author  (use select_related for single JOIN)
      - ManyToMany  → Tag     (use prefetch_related for separate query)
    """

    title: str = models.CharField(max_length=200)
    author: Author = models.ForeignKey(
        Author, on_delete=models.CASCADE, related_name="books"
    )
    tags = models.ManyToManyField(Tag, blank=True)
    sales_count: int = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "library"

    def __str__(self) -> str:
        return self.title


class UserProfile(models.Model):
    """Extended profile linked to Django's auth.User via OneToOneField."""

    # Referencing auth.User by string to avoid a hard import cycle.
    user = models.OneToOneField(
        "auth.User", on_delete=models.CASCADE, related_name="profile"
    )
    bio: str = models.TextField(blank=True)
    image: Optional[str] = models.ImageField(
        upload_to="profiles/", null=True, blank=True
    )

    class Meta:
        app_label = "accounts"


# ==========================================================================
# 2. CUSTOM QUERYSET AND MANAGER (Topic 3 & 6 from theory)
# ==========================================================================

class ActiveQuerySet(models.QuerySet):
    """
    Chainable methods that encode common business filters.
    Attach this to any model that has is_active / deleted_at / created_at.
    """

    def active(self) -> "ActiveQuerySet":
        """Exclude soft-deleted and inactive records."""
        return self.filter(is_active=True, deleted_at__isnull=True)

    def by_user(self, user: "models.Model") -> "ActiveQuerySet":
        """Narrow the queryset to records belonging to a specific user."""
        return self.filter(user=user)

    def recent(self, days: int = 30) -> "ActiveQuerySet":
        """Records created within the last *days* calendar days."""
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(created_at__gte=cutoff)


class OrderQuerySet(models.QuerySet):
    """Business-level queryset for the Order model."""

    def pending(self) -> "OrderQuerySet":
        return self.filter(status="pending")

    def with_totals(self) -> "OrderQuerySet":
        """
        Annotate each order with an item count and the total price of its
        line items — a single extra JOIN instead of per-order Python logic.
        """
        return self.annotate(
            item_count=Count("items"),
            total=Sum("items__price"),
        )


class OrderManager(models.Manager):
    """
    Custom manager that exposes OrderQuerySet methods directly on the model
    class, so callers can write Order.objects.pending() without going through
    .get_queryset() first.
    """

    def get_queryset(self) -> OrderQuerySet:
        return OrderQuerySet(self.model, using=self._db)

    def pending(self) -> OrderQuerySet:
        return self.get_queryset().pending()

    def high_value(self, threshold: int = 1000) -> OrderQuerySet:
        """Orders whose amount is at or above *threshold*."""
        return self.get_queryset().filter(amount__gte=threshold)


class Order(models.Model):
    """
    E-commerce order model.  Demonstrates:
      - Custom manager (objects = OrderManager())
      - select_for_update() usage for row-level locking
      - aggregate() for whole-queryset statistics
    """

    user = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, related_name="orders"
    )
    amount: Decimal = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal: Decimal = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    tax_amount: Decimal = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    status: str = models.CharField(max_length=50, default="pending")
    is_active: bool = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    shipping_address = models.ForeignKey(
        "ShippingAddress",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )

    # Replace the default manager with the custom one.
    objects = OrderManager()

    class Meta:
        app_label = "shop"


class ShippingAddress(models.Model):
    """Postal address for order delivery."""

    street: str = models.CharField(max_length=255)
    city: str = models.CharField(max_length=100)
    country: str = models.CharField(max_length=100)

    class Meta:
        app_label = "shop"


class Product(models.Model):
    """
    Product catalogue entry.  Demonstrates F() expressions for column-level
    arithmetic and comparison without loading data into Python.
    """

    name: str = models.CharField(max_length=200)
    price: Decimal = models.DecimalField(max_digits=10, decimal_places=2)
    original_price: Decimal = models.DecimalField(max_digits=10, decimal_places=2)
    sale_price: Decimal = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        app_label = "shop"


# ==========================================================================
# 3. N+1 PROBLEM — select_related vs prefetch_related
# ==========================================================================

def demonstrate_n_plus_one_bad() -> None:
    """
    Anti-pattern: accessing book.author inside a loop triggers one extra
    SQL query per book — 100 books → 101 total queries.

    NOTE: This function is illustrative only; it requires a running database.
    """
    books = Book.objects.all()
    for book in books:
        # Each access hits the database again because author is not cached.
        print(book.author.name)  # N additional queries — avoid this pattern.


def demonstrate_select_related() -> None:
    """
    Fix for ForeignKey / OneToOne relations: select_related() issues a single
    SQL JOIN, so all author data is fetched in one query regardless of how
    many books are in the queryset.
    """
    books = Book.objects.select_related("author").all()
    for book in books:
        print(book.author.name)  # No extra query — author already joined.


def demonstrate_prefetch_related() -> None:
    """
    Fix for ManyToMany / reverse FK relations: prefetch_related() issues a
    second query that fetches all related objects and then matches them in
    Python — exactly 2 queries total, not 1 + N.
    """
    books = (
        Book.objects
        .select_related("author")           # 1 JOIN for ForeignKey
        .prefetch_related("tags")           # 1 extra query for ManyToMany
        .all()
    )
    for book in books:
        print(book.author.name)
        for tag in book.tags.all():         # No database hit — already cached.
            print(f"  tag: {tag.name}")


def demonstrate_nested_select_related() -> None:
    """
    Chaining double-underscore paths in select_related() follows relations
    across multiple hops in a single query — user → profile, shipping_address.
    """
    orders = Order.objects.select_related(
        "user",                 # auth.User JOIN
        "user__profile",        # UserProfile JOIN (nested one hop further)
        "shipping_address",     # ShippingAddress JOIN
    ).all()

    for order in orders:
        print(order.user.username)
        print(order.shipping_address.city if order.shipping_address else "—")


# ==========================================================================
# 4. AGGREGATE vs ANNOTATE
# ==========================================================================

def demonstrate_aggregate() -> dict:
    """
    aggregate() collapses the entire queryset into a single Python dict.
    Use it when you need summary statistics for a whole table or filtered set.

    Returns a dict such as:
        {"total_orders": 500, "total_revenue": 250000.0, "avg_order_value": 500.0,
         "max_order": 9999.0}
    """
    stats = Order.objects.aggregate(
        total_orders=Count("id"),
        total_revenue=Sum("amount"),
        avg_order_value=Avg("amount"),
        max_order=Max("amount"),
        min_order=Min("amount"),
    )
    return stats


def demonstrate_annotate() -> None:
    """
    annotate() adds a computed column to *each row* in the queryset.
    The result is still a queryset — you can filter, order, or slice it.

    Here, each Author object gains:
      - book_count  — number of books they have written
      - total_sales — sum of sales_count across all their books
    """
    authors = Author.objects.annotate(
        book_count=Count("books"),
        total_sales=Sum("books__sales_count"),
    ).order_by("-book_count")

    for author in authors:
        print(
            f"{author.name}: {author.book_count} books, "
            f"{author.total_sales} total sales"
        )


# ==========================================================================
# 5. F EXPRESSIONS — column arithmetic inside the database
# ==========================================================================

def apply_price_increase(percent: float = 10.0) -> int:
    """
    Increase the price of every Product by *percent* without loading a single
    model instance into Python — the arithmetic happens entirely in SQL.

    Returns the number of rows updated.
    """
    multiplier = Decimal(str(1 + percent / 100))
    return Product.objects.update(price=F("price") * multiplier)


def find_heavily_discounted_products(discount_threshold: float = 0.20) -> models.QuerySet:
    """
    Return products whose sale_price is more than *discount_threshold* below
    original_price, using F() to compare two columns directly in SQL.

    Example: discount_threshold=0.20 → products at least 20% off.
    """
    factor = Decimal(str(1 - discount_threshold))
    return Product.objects.filter(sale_price__lt=F("original_price") * factor)


# ==========================================================================
# 6. Q OBJECTS — complex filter compositions
# ==========================================================================

def get_premium_or_admin_users() -> models.QuerySet:
    """
    OR query: return users who are either on a premium plan OR have admin role.
    Without Q objects this would require two separate querysets and a union.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.filter(
        Q(profile__plan="premium") | Q(is_staff=True)
    )


def get_active_non_trial_users() -> models.QuerySet:
    """
    AND + NOT query: active users who are NOT on a trial plan.
    ~Q() is the ORM equivalent of SQL NOT (...).
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.filter(
        Q(is_active=True) & ~Q(profile__plan="trial")
    )


# ==========================================================================
# 7. ORM PERFORMANCE TOOLKIT
# ==========================================================================

def load_only_required_fields() -> models.QuerySet:
    """
    only() fetches a subset of columns.  Accessing a deferred field later
    triggers an additional query per instance — only() is best when you are
    certain you will not touch the omitted fields.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.only("id", "username", "email")


def defer_heavy_fields() -> models.QuerySet:
    """
    defer() is the inverse of only(): load everything except the listed
    columns.  Useful when a model has one or two large text/blob columns
    that are rarely needed in list views.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.defer("last_login", "date_joined")


def get_emails_as_flat_list() -> models.QuerySet:
    """
    values_list(flat=True) returns a flat ValuesQuerySet of scalars — no
    model instantiation overhead.  Ideal for ID lists or simple lookups.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.filter(is_active=True).values_list("email", flat=True)


def get_user_dicts() -> models.QuerySet:
    """
    values() returns dicts instead of model instances.  Fastest path when
    you only need to serialize data (e.g., pass directly to a DRF serializer
    or build a JSON response without full model overhead).
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.values("id", "username", "email")


def process_large_queryset_with_iterator() -> None:
    """
    iterator() streams rows from the database in chunks instead of caching the
    entire result set in memory.  Critical for large tables — without it Django
    loads every row before the first iteration begins.

    chunk_size controls how many rows are fetched per round-trip.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    for user in User.objects.filter(is_active=True).iterator(chunk_size=500):
        # process(user) — placeholder for your real per-row logic
        _ = user.username  # no-op to satisfy linters


def check_pending_orders_exist(user: "models.Model") -> bool:
    """
    exists() is faster than count() > 0 or bool(queryset) because the
    database can stop scanning after finding the first matching row.
    """
    return Order.objects.filter(user=user, status="pending").exists()


def bulk_create_users(count: int = 1000) -> List["models.Model"]:
    """
    bulk_create() inserts multiple rows in a single SQL INSERT statement.
    batch_size prevents the SQL statement from becoming too large for very
    big lists.

    Returns the list of created instances (PKs populated on PostgreSQL).
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    users = [
        User(username=f"user_{i}", email=f"u{i}@example.com")
        for i in range(count)
    ]
    return User.objects.bulk_create(users, batch_size=100)


def bulk_update_emails(users: List["models.Model"]) -> int:
    """
    bulk_update() issues a single UPDATE for a list of model instances.
    Only the listed fields are written — safer and faster than saving each
    instance individually.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    for user in users:
        user.email = user.email.lower()  # normalise to lowercase
    return User.objects.bulk_update(users, ["email"], batch_size=100)


def process_order_with_row_lock(order_id: int) -> None:
    """
    select_for_update() acquires a row-level database lock for the duration
    of the enclosing atomic() block.  This prevents two concurrent requests
    from reading stale status and both transitioning the same order to
    'processing' simultaneously (classic lost-update race condition).

    Must be wrapped in transaction.atomic().
    """
    with transaction.atomic():
        order = Order.objects.select_for_update().get(id=order_id)
        if order.status == "pending":
            order.status = "processing"
            order.save(update_fields=["status"])


def explain_queryset(queryset: models.QuerySet) -> None:
    """
    Run EXPLAIN ANALYZE on the underlying SQL to inspect query plans and
    spot missing indexes.  Works on PostgreSQL; on SQLite/MySQL the ANALYZE
    keyword should be dropped.

    NOTE: Requires an active database connection.
    """
    from django.db import connection

    sql = str(queryset.query)
    with connection.cursor() as cursor:
        cursor.execute(f"EXPLAIN ANALYZE {sql}")
        rows = cursor.fetchall()
    for row in rows:
        print(row[0])


# ==========================================================================
# 8. DJANGO SIGNALS
# ==========================================================================

# --- Built-in signal handlers ---

@receiver(post_save, sender="auth.User")
def create_user_profile(
    sender: type,
    instance: "models.Model",
    created: bool,
    **kwargs: object,
) -> None:
    """
    Automatically create a UserProfile the first time a User is saved.
    The *created* flag distinguishes INSERT (True) from UPDATE (False) so that
    subsequent saves do not attempt to create duplicate profiles.
    """
    if created:
        UserProfile.objects.create(user=instance)


@receiver(pre_save, sender=Order)
def calculate_tax(
    sender: type,
    instance: Order,
    **kwargs: object,
) -> None:
    """
    Compute tax before every Order save if tax_amount has not been set
    explicitly.  18 % is used as the illustrative rate.
    """
    if not instance.tax_amount:
        instance.tax_amount = instance.subtotal * Decimal("0.18")


@receiver(post_delete, sender=UserProfile)
def delete_profile_image(
    sender: type,
    instance: UserProfile,
    **kwargs: object,
) -> None:
    """
    Clean up the profile image file from storage when a UserProfile is
    deleted.  Passing save=False prevents a recursive save call.
    """
    if instance.image:
        instance.image.delete(save=False)


# --- Custom signal definition and usage ---

# Declare the signal at module level so senders and receivers can import it.
order_placed = Signal()


def place_new_order(order: Order, user: "models.Model") -> None:
    """
    Business function that finalises an order and emits the custom
    order_placed signal.  Any registered receivers (email, inventory, etc.)
    are invoked synchronously before this function returns.
    """
    order.status = "confirmed"
    order.save(update_fields=["status"])

    # Emit the custom signal — all receivers are called in registration order.
    order_placed.send(sender=Order, order=order, user=user)


@receiver(order_placed)
def on_order_placed_send_email(
    sender: type,
    order: Order,
    user: "models.Model",
    **kwargs: object,
) -> None:
    """
    Send an order-confirmation email in response to the order_placed signal.
    Keeping this in a separate receiver (rather than inside place_new_order)
    preserves loose coupling — the email concern is decoupled from the
    order-saving logic.
    """
    logger.info(
        "order_placed signal: sending confirmation email",
        extra={"user_id": getattr(user, "pk", None), "order_id": order.pk},
    )
    # send_order_confirmation_email(user.email, order)  # call your email service here


@receiver(order_placed)
def on_order_placed_update_inventory(
    sender: type,
    order: Order,
    user: "models.Model",
    **kwargs: object,
) -> None:
    """
    Decrement inventory levels for every line item when an order is placed.
    Registered as a separate receiver from the email handler — each concern
    stays isolated and independently testable.
    """
    logger.info(
        "order_placed signal: updating inventory",
        extra={"order_id": order.pk},
    )
    # update_inventory(order.items.all())  # call your inventory service here


# ==========================================================================
# 9. SIGNAL DESIGN GUIDELINES (as inline reference)
# ==========================================================================

SIGNAL_DESIGN_NOTES = """
When to use Django signals:
  - Loose coupling between models that live in different apps
  - Extending a third-party app without modifying its source
  - Cross-cutting concerns (audit logging, notifications, cache invalidation)

When NOT to use signals:
  - Core business logic that must be easy to trace and test — use a service
    layer or a domain function instead; signals make call stacks hard to follow.
  - Heavy / long-running operations — defer them to a Celery task to avoid
    blocking the HTTP response cycle.
  - Cases where the sender and receiver are in the same app — a direct function
    call is simpler and easier to debug.
"""


# ==========================================================================
# 10. QUICK-REFERENCE: MANAGER USAGE PATTERNS
# ==========================================================================

MANAGER_USAGE_EXAMPLES = """
# Calling custom manager methods directly:
Order.objects.pending()                         # → pending orders queryset
Order.objects.high_value(500)                   # → orders with amount >= 500

# Chaining QuerySet methods (requires get_queryset() to return OrderQuerySet):
Order.objects.get_queryset().pending().with_totals()

# Using ActiveQuerySet (if wired to a model via as_manager()):
SomeModel.objects.active().recent(7).by_user(request.user)
"""
