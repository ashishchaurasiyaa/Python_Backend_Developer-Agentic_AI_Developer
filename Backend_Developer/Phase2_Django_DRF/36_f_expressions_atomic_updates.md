# F-Expressions & Atomic Updates — Race-Free Patterns

## Why It Matters

Concurrent updates = lost update bugs:
- Two requests both add to counter → one increment lost
- Inventory race → oversold
- Balance update → money disappears

Solution: atomic DB-side ops via F-expressions or single-statement updates.

Senior interview: "Counter increment across 1000 concurrent users — how?" → F-expression.

---

## Core Concepts

### Lost Update Demo

```python
# WRONG — race condition
def increment_view(article_id):
    article = Article.objects.get(pk=article_id)   # READ
    article.view_count += 1                         # MODIFY
    article.save()                                   # WRITE


# Two concurrent calls:
# A: read view_count=10
# B: read view_count=10
# A: write 11
# B: write 11   ← B's update lost; should be 12
```

### F-Expression (Atomic)

```python
from django.db.models import F


# RIGHT — atomic SQL UPDATE
def increment_view(article_id):
    Article.objects.filter(pk=article_id).update(view_count=F('view_count') + 1)


# Generated SQL:
# UPDATE article SET view_count = view_count + 1 WHERE id = X
# Atomic at DB level — no race
```

### F in update()

```python
# Increment by N
Article.objects.filter(pk=1).update(view_count=F('view_count') + N)


# Cross-field reference
Order.objects.update(
    total=F('subtotal') + F('tax') - F('discount'),
)


# Complex math
Account.objects.filter(pk=1).update(
    balance=F('balance') * Decimal('1.05'),   # 5% interest
)


# Conditional update (with When/Case)
from django.db.models import Case, When, Value, IntegerField


Article.objects.update(
    priority=Case(
        When(views__gte=10000, then=Value(1)),
        When(views__gte=1000, then=Value(2)),
        default=Value(3),
        output_field=IntegerField(),
    )
)
```

### F in filter()

```python
# Compare fields
Article.objects.filter(updated_at__gt=F('created_at'))
# Articles that were modified after creation


# Self-referential filter
Order.objects.filter(amount__gt=F('refund_amount'))
```

### F in annotate

```python
from django.db.models import F, ExpressionWrapper, FloatField


Article.objects.annotate(
    engagement_score=F('likes') * 2 + F('comments') * 5 + F('shares') * 3
).order_by('-engagement_score')


# Computed percentage
Order.objects.annotate(
    discount_pct=ExpressionWrapper(
        F('discount') * 100.0 / F('subtotal'),
        output_field=FloatField(),
    )
).filter(discount_pct__gte=20)
```

### Atomic Conditional Update

```python
# Decrement only if stock > 0
def reserve_one(product_id):
    updated = Product.objects.filter(
        pk=product_id,
        stock__gt=0,
    ).update(stock=F('stock') - 1)

    if updated == 0:
        raise OutOfStock()
    return True


# Race-condition-free:
# - WHERE clause filters in same atomic UPDATE
# - If stock=0, no rows updated, function returns OutOfStock
# - Two concurrent calls: only one succeeds when stock=1
```

### `update_or_create` (Atomic Upsert)

```python
obj, created = Article.objects.update_or_create(
    slug='hello-world',
    defaults={'title': 'Hello', 'body': '...'},
)
# Atomic at DB level (PostgreSQL ON CONFLICT)
```

### `get_or_create` (Pseudo-Atomic)

```python
obj, created = Tag.objects.get_or_create(name='python')
# Not 100% atomic — race possible between GET and CREATE
# Use unique constraint + handle IntegrityError
```

### Atomic via UPSERT

```python
# PostgreSQL ON CONFLICT (via raw SQL or Django 4.1+)
from django.db.models import F


# bulk_create with conflict handling (Django 4.1+)
Article.objects.bulk_create(
    objects,
    update_conflicts=True,
    update_fields=['title', 'view_count'],
    unique_fields=['slug'],
)
```

### Limitations of F Expressions

**F can't be used after instance modification:**

```python
# WRONG
article.view_count = F('view_count') + 1
article.save()
article.view_count   # this is F expression object, not int!
# Subsequent ops on article.view_count fail


# Refresh from DB
article.refresh_from_db()
print(article.view_count)   # now int
```

### `refresh_from_db()`

```python
Article.objects.filter(pk=1).update(view_count=F('view_count') + 1)


article = Article.objects.get(pk=1)   # fresh read
# OR
article.refresh_from_db()
```

### Window Functions for Ranking

```python
from django.db.models import Window, F
from django.db.models.functions import Rank


# Add rank without storing it
articles_with_rank = Article.objects.annotate(
    rank=Window(
        expression=Rank(),
        order_by=F('view_count').desc(),
    )
)
```

### `OuterRef` + `Subquery` for Atomic Cross-Table Updates

```python
# Update each user's order_count with current count of their orders
from django.db.models import Subquery, OuterRef, Count


order_count = Order.objects.filter(user=OuterRef('pk')).values('user').annotate(c=Count('*')).values('c')


User.objects.update(
    order_count=Subquery(order_count),
)
```

### Transactions vs F-Expressions

| Pattern | Use Case |
|---|---|
| F-expression in `.update()` | Single-statement atomic ops (counter, increment) |
| `transaction.atomic` + `select_for_update` | Multi-step read-modify-write |
| Optimistic locking (version column) | High contention, retries OK |

F-expression preferred when simple — no transaction overhead.

---

## Common Pitfalls

### 1. Instance Save with F

```python
article.view_count = F('view_count') + 1
article.save()
# article.view_count is now expression object, not int
article.view_count + 1   # ERROR
```

Use refresh_from_db or queryset update.

### 2. F in Default Values

```python
class Order(models.Model):
    total = models.IntegerField(default=F('subtotal'))   # ERROR — F can't be default
```

### 3. F with Decimal vs Float

```python
Account.objects.update(balance=F('balance') * 1.05)
```

Float arithmetic on Decimal → precision loss. Use `Decimal`:

```python
from decimal import Decimal
Account.objects.update(balance=F('balance') * Decimal('1.05'))
```

### 4. F Without Output Field for Complex Expressions

```python
F('a') / F('b')   # may infer wrong type
```

Use ExpressionWrapper:

```python
from django.db.models import ExpressionWrapper, FloatField


ExpressionWrapper(F('a') / F('b'), output_field=FloatField())
```

### 5. Mixing F with Pre-Computed Values

```python
new_views = some_calc()
Article.objects.filter(pk=1).update(views=F('views') + new_views)
```

OK if `new_views` from outside DB. Mixing computed Python with F → ensure no race in the calc itself.

### 6. update() Doesn't Call save() / Signals

```python
Article.objects.filter(pk=1).update(view_count=F('view_count') + 1)
# post_save signal NOT fired
# .save() override NOT called
```

For business logic that needs signals, use `.save()` with refetch.

---

## Interview Q&A

**Q1:** Lost update problem solve karne ke options?
**A:** (1) **F-expression**: single SQL UPDATE — atomic. (2) **SELECT FOR UPDATE**: pessimistic lock. (3) **Optimistic locking**: version column + retry on conflict. F-expression simplest + fastest for counter-like ops. Pessimistic for multi-step. Optimistic for low-contention.

**Q2:** F-expression kab use, kab pessimistic lock?
**A:** F: simple updates (`field = field + 1`, `total = subtotal + tax`). One SQL statement. Pessimistic: read-modify-write needs validation (`if balance < amount: raise; balance -= amount`). Multi-step logic. F-expression can't handle "check then update" — need pessimistic or atomic conditional update.

**Q3:** Atomic conditional decrement (inventory)?
**A:**
```python
updated = Product.objects.filter(pk=X, stock__gt=0).update(stock=F('stock') - 1)
if updated == 0:
    raise OutOfStock()
```
Single SQL, atomic. WHERE checks + UPDATE in one operation. Two concurrent calls: only one succeeds when stock was 1.

**Q4:** F-expression vs `update()` direct value?
**A:** Direct value: `update(views=10)` — sets to 10. F: `update(views=F('views') + 1)` — increments current value. F is critical when you don't know current value and need atomic increment. Direct OK when value computed elsewhere or always set.

**Q5:** Refresh from DB after F update?
**A:** After `qs.update()`, instance still has stale value. To access fresh: `article.refresh_from_db()` OR re-fetch `article = Article.objects.get(pk=...)`. For loops processing many: re-fetch via PKs at end, or use `update().returning()` (Django 4.2+).

**Q6:** Bulk atomic ops?
**A:** `bulk_update` for multi-row updates. For idempotent inserts: `bulk_create(update_conflicts=True, update_fields=[...], unique_fields=[...])` — uses PostgreSQL ON CONFLICT. For aggregation: `update(field=F('field') + Subquery(...))`.

**Q7:** F-expression Decimal precision?
**A:** Mixing F with float can lose precision. Always use `Decimal` literals:
```python
from decimal import Decimal
balance=F('balance') * Decimal('1.05')   # exact
```
Float `1.05` may give `1.04999...`.

**Q8:** When NOT to use F-expression?
**A:** When you need to validate against current value before update (e.g., "if balance >= amount"). F can't do conditional check. Use atomic UPDATE with WHERE (single SQL):
```python
updated = Account.objects.filter(pk=X, balance__gte=amount).update(balance=F('balance') - amount)
```
Or pessimistic lock + multi-step.

---

## Real-World Use Cases

### 1. View Counter

```python
def article_detail(request, pk):
    article = Article.objects.get(pk=pk)
    Article.objects.filter(pk=pk).update(view_count=F('view_count') + 1)
    return render(request, 'detail.html', {'article': article})
```

### 2. Atomic Money Transfer

```python
@transaction.atomic
def transfer(from_id, to_id, amount):
    # Atomic check + debit
    updated = Account.objects.filter(
        pk=from_id, balance__gte=amount,
    ).update(balance=F('balance') - amount)

    if updated == 0:
        raise InsufficientFunds()

    # Credit (no check needed)
    Account.objects.filter(pk=to_id).update(balance=F('balance') + amount)
```

### 3. Bulk Score Recalculation

```python
# Each row computed from its own fields
Article.objects.update(
    engagement_score=F('likes') * 2 + F('comments') * 5 + F('shares') * 3
)
# Single SQL UPDATE — fast
```

### 4. Update Total Based on Children

```python
# Update each user's order_count to current count of their orders
from django.db.models import Subquery, OuterRef, Count


count_subq = Order.objects.filter(user=OuterRef('pk')).values('user').annotate(c=Count('*')).values('c')


User.objects.update(order_count=Subquery(count_subq))
```

---

## References

- [F() expressions](https://docs.djangoproject.com/en/5.0/ref/models/expressions/#f-expressions)
- [Atomic transactions](https://docs.djangoproject.com/en/5.0/topics/db/transactions/)
- [Conditional expressions](https://docs.djangoproject.com/en/5.0/ref/models/conditional-expressions/)
- "Two Scoops of Django" — atomic ops chapter
