"""
F-Expressions & Atomic Updates — Production Patterns
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import (
    F, Q,
    Sum, Count, Avg, Max,
    Case, When, Value, IntegerField, DecimalField, FloatField, BooleanField,
    ExpressionWrapper,
    Subquery, OuterRef, Exists,
)


# ==========================================================================
# 1. BASIC F-EXPRESSION (atomic increment)
# ==========================================================================

def atomic_increment_view_count(article_id):
    """Single SQL UPDATE — race-condition-free."""
    # from blog.models import Article
    Article.objects.filter(pk=article_id).update(view_count=F('view_count') + 1)
    # SQL: UPDATE article SET view_count = view_count + 1 WHERE id = X


def atomic_increment_by(article_id, n):
    Article.objects.filter(pk=article_id).update(view_count=F('view_count') + n)


# ==========================================================================
# 2. ATOMIC CONDITIONAL UPDATE (no race)
# ==========================================================================

def reserve_one(product_id):
    """Atomic check + decrement in single SQL."""
    # from blog.models import Product

    updated = Product.objects.filter(
        pk=product_id,
        stock__gt=0,
    ).update(stock=F('stock') - 1)

    if updated == 0:
        raise OutOfStock()

    return True


def reserve_n(product_id, qty):
    """Reserve qty units atomically."""
    updated = Product.objects.filter(
        pk=product_id,
        stock__gte=qty,
    ).update(stock=F('stock') - qty)

    return updated == 1


class OutOfStock(Exception):
    pass


# ==========================================================================
# 3. CROSS-FIELD REFERENCES
# ==========================================================================

def recompute_order_totals():
    """Each order's total = subtotal + tax - discount."""
    # from blog.models import Order
    Order.objects.update(
        total=F('subtotal') + F('tax') - F('discount'),
    )


def filter_modified_orders():
    """Orders modified after creation."""
    return Order.objects.filter(updated_at__gt=F('created_at'))


def filter_partial_refunds():
    """Orders where refund < amount."""
    return Order.objects.filter(refund_amount__gt=0, refund_amount__lt=F('amount'))


# ==========================================================================
# 4. DECIMAL ARITHMETIC (precision matters)
# ==========================================================================

def apply_interest(account_id, rate=Decimal('0.05')):
    """5% interest — use Decimal not float."""
    Account.objects.filter(pk=account_id).update(
        balance=F('balance') * (Decimal('1') + rate),
    )


def apply_discount(order_id, pct=Decimal('10')):
    Order.objects.filter(pk=order_id).update(
        total=F('subtotal') * (Decimal('1') - pct / Decimal('100')),
    )


# ==========================================================================
# 5. F IN ANNOTATIONS
# ==========================================================================

def annotated_engagement():
    """Each article gets a computed engagement score."""
    return Article.objects.annotate(
        engagement_score=F('likes') * 2 + F('comments') * 5 + F('shares') * 3,
    ).order_by('-engagement_score')


def annotated_percentage():
    """Discount as percentage with explicit output type."""
    return Order.objects.annotate(
        discount_pct=ExpressionWrapper(
            F('discount') * 100.0 / F('subtotal'),
            output_field=FloatField(),
        ),
    ).filter(discount_pct__gte=20)


# ==========================================================================
# 6. CASE/WHEN (conditional update)
# ==========================================================================

def categorize_articles_by_views():
    """Set priority based on view tier."""
    Article.objects.update(
        priority=Case(
            When(view_count__gte=10000, then=Value(1)),
            When(view_count__gte=1000, then=Value(2)),
            When(view_count__gte=100, then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        ),
    )


def flag_inactive_users():
    """Mark users as inactive if last_login > 90 days."""
    from django.utils import timezone
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=90)

    User.objects.update(
        is_active=Case(
            When(last_login__lt=cutoff, then=Value(False)),
            default=F('is_active'),
            output_field=BooleanField(),
        ),
    )


# ==========================================================================
# 7. MONEY TRANSFER (atomic with check)
# ==========================================================================

@transaction.atomic
def transfer_money(from_id, to_id, amount):
    """Race-condition-free transfer."""
    # Atomic debit with insufficient funds check
    debited = Account.objects.filter(
        pk=from_id,
        balance__gte=amount,
    ).update(balance=F('balance') - amount)

    if debited == 0:
        raise ValueError('Insufficient funds or account not found')

    # Credit (no check needed)
    Account.objects.filter(pk=to_id).update(balance=F('balance') + amount)

    # Audit log
    Transaction.objects.create(
        from_account_id=from_id,
        to_account_id=to_id,
        amount=amount,
    )


# ==========================================================================
# 8. SUBQUERY UPDATE (cross-table)
# ==========================================================================

def update_user_order_counts():
    """Update each user's denormalized order_count."""
    order_count = (
        Order.objects
        .filter(user=OuterRef('pk'))
        .values('user')
        .annotate(c=Count('*'))
        .values('c')
    )

    User.objects.update(order_count=Subquery(order_count))


def update_users_with_recent_order_flag():
    """Set has_recent_order=True if any order in last 30 days."""
    from django.utils import timezone
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=30)
    recent_orders = Order.objects.filter(
        user=OuterRef('pk'),
        created_at__gte=cutoff,
    )

    User.objects.update(
        has_recent_order=Exists(recent_orders),
    )


# ==========================================================================
# 9. BULK UPDATE WITH F
# ==========================================================================

def bump_all_articles_view_count():
    """Add 1 to every article's view count (e.g., system-wide tracking)."""
    Article.objects.update(view_count=F('view_count') + 1)


def increment_users_login_count_for_today():
    """Increment login count for users who logged in today."""
    from django.utils import timezone
    today = timezone.now().date()

    User.objects.filter(last_login__date=today).update(
        login_count=F('login_count') + 1,
    )


# ==========================================================================
# 10. UPSERT (insert or update)
# ==========================================================================

def upsert_article(slug, title, body):
    """update_or_create — atomic via PostgreSQL ON CONFLICT."""
    article, created = Article.objects.update_or_create(
        slug=slug,
        defaults={'title': title, 'body': body},
    )
    return article, created


def bulk_upsert_articles(article_list):
    """Bulk insert + update on conflict (Django 4.1+)."""
    Article.objects.bulk_create(
        article_list,
        update_conflicts=True,
        update_fields=['title', 'body', 'updated_at'],
        unique_fields=['slug'],
    )


# ==========================================================================
# 11. ATOMIC RATE LIMIT VIA F
# ==========================================================================

def consume_quota(user_id, amount=1):
    """Atomic quota consumption."""
    updated = (
        UserQuota.objects
        .filter(user_id=user_id, remaining__gte=amount)
        .update(remaining=F('remaining') - amount)
    )
    return updated == 1


def reset_quotas_daily():
    """Daily quota reset — single SQL."""
    UserQuota.objects.update(remaining=F('daily_limit'))


# ==========================================================================
# 12. REFRESH AFTER F UPDATE
# ==========================================================================

def update_and_get_fresh(article_id):
    """After F update, refresh to get actual value."""
    Article.objects.filter(pk=article_id).update(
        view_count=F('view_count') + 1,
    )

    article = Article.objects.get(pk=article_id)
    return article.view_count

    # Alternative: instance refresh
    # article = Article.objects.get(pk=article_id)
    # Article.objects.filter(pk=article_id).update(view_count=F('view_count') + 1)
    # article.refresh_from_db()
    # return article.view_count


# ==========================================================================
# 13. WINDOW FUNCTIONS (Django 4+)
# ==========================================================================

from django.db.models import Window
from django.db.models.functions import Rank, DenseRank, RowNumber, Lag, Lead


def articles_ranked_by_views():
    """Add rank field showing position by views."""
    return Article.objects.annotate(
        rank=Window(
            expression=Rank(),
            order_by=F('view_count').desc(),
        ),
    )


def top_per_category():
    """Top 3 articles per category."""
    qs = Article.objects.annotate(
        rn=Window(
            expression=RowNumber(),
            partition_by=[F('category')],
            order_by=F('view_count').desc(),
        ),
    )
    # Filter via wrapping (window can't be in WHERE directly)
    top_ids = [a.pk for a in qs if a.rn <= 3]
    return Article.objects.filter(pk__in=top_ids)


def each_order_with_previous():
    """Compare each order to previous one (same user)."""
    return Order.objects.annotate(
        prev_amount=Window(
            expression=Lag('amount'),
            partition_by=[F('user_id')],
            order_by=F('created_at'),
        ),
    )


# ==========================================================================
# 14. PESSIMISTIC vs OPTIMISTIC COMPARISON
# ==========================================================================

# Pessimistic — locks row
@transaction.atomic
def buy_pessimistic(product_id):
    product = Product.objects.select_for_update().get(pk=product_id)
    if product.stock <= 0:
        raise OutOfStock()
    product.stock -= 1
    product.save()


# Optimistic — F-expression (no lock)
def buy_atomic(product_id):
    """Faster than pessimistic — no lock contention."""
    updated = Product.objects.filter(
        pk=product_id,
        stock__gt=0,
    ).update(stock=F('stock') - 1)

    if updated == 0:
        raise OutOfStock()


# Optimistic — version column + retry
def buy_optimistic(product_id, max_retries=3):
    import time, random

    for attempt in range(max_retries):
        product = Product.objects.get(pk=product_id)
        if product.stock <= 0:
            raise OutOfStock()

        updated = Product.objects.filter(
            pk=product_id,
            version=product.version,
        ).update(
            stock=F('stock') - 1,
            version=F('version') + 1,
        )

        if updated == 1:
            return
        time.sleep(0.05 * (2 ** attempt) + random.random() * 0.05)

    raise ConcurrencyError('Max retries')


class ConcurrencyError(Exception):
    pass


# ==========================================================================
# 15. PERFORMANCE COMPARISON
# ==========================================================================

PERFORMANCE_NOTES = """
F-expression `update()`:
- 1 SQL statement, atomic
- No transaction overhead
- No row lock (uses InnoDB row-level for the update)
- Fastest for simple atomic ops

select_for_update + save():
- 2 SQL statements (SELECT + UPDATE) + lock
- Held until commit
- Other readers wait
- Use only when multi-step logic needed

Version column + retry:
- 2 statements + retries on conflict
- No held lock — best throughput
- Wasted work on retries
- Use for low-contention with complex logic

Choose:
- Counter increments → F-expression
- "if stock > 0: stock -= 1" → atomic UPDATE with WHERE
- Multi-step with external API → select_for_update or version
- High contention + simple op → F (no lock)
"""
