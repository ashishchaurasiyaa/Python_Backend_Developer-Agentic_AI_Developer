# Django ORM — select_related, prefetch_related, annotate, aggregate

## Quick Concepts
- **select_related** = SQL JOIN karta hai — ForeignKey/OneToOne ke liye (single query)
- **prefetch_related** = alag query karta hai — ManyToMany/reverse FK ke liye (2 queries)
- **annotate** = har row mein calculated field add karo
- **aggregate** = poore queryset ka ek value (SUM, COUNT, AVG)
- **Custom Manager** = queryset logic reuse karo

---

## Interview Questions & Answers

### Q1: N+1 problem kya hai? select_related aur prefetch_related se kaise fix karte hain?
**Answer:**
N+1: 1 query for list + N queries for each item's relation = N+1 total queries.

```python
# Models
class Author(models.Model):
    name = models.CharField(max_length=100)

class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
    tags = models.ManyToManyField("Tag")

class Tag(models.Model):
    name = models.CharField(max_length=50)

# BAD — N+1 problem (100 books = 101 queries)
books = Book.objects.all()
for book in books:
    print(book.author.name)  # har book ke liye ek alag query!

# GOOD — select_related (ForeignKey/OneToOne — JOIN)
books = Book.objects.select_related("author").all()
for book in books:
    print(book.author.name)  # single query with JOIN

# GOOD — prefetch_related (ManyToMany / reverse FK)
books = Book.objects.prefetch_related("tags").select_related("author").all()
for book in books:
    print(book.author.name)
    for tag in book.tags.all():   # no extra query
        print(tag.name)

# Nested select_related
orders = Order.objects.select_related(
    "user",
    "user__profile",    # nested relation
    "shipping_address"
).all()
```

---

### Q2: annotate aur aggregate ka fark kya hai? Examples?
**Answer:**
```python
from django.db.models import Count, Sum, Avg, Max, Min, F, Q

# AGGREGATE — ek single value return karta hai (whole queryset)
from django.db.models import Count, Sum, Avg

stats = Order.objects.aggregate(
    total_orders=Count("id"),
    total_revenue=Sum("amount"),
    avg_order_value=Avg("amount"),
    max_order=Max("amount"),
)
# Returns: {"total_orders": 500, "total_revenue": 250000.0, ...}

# ANNOTATE — har row mein ek calculated column add karta hai
authors = Author.objects.annotate(
    book_count=Count("books"),
    total_sales=Sum("books__sales_count"),
).order_by("-book_count")

for author in authors:
    print(f"{author.name}: {author.book_count} books, {author.total_sales} sales")

# F expression — column ki value use karo without Python
# Price 10% badhao
Product.objects.update(price=F("price") * 1.10)

# Two columns compare karo
discounted = Product.objects.filter(sale_price__lt=F("original_price") * 0.8)

# Q objects — complex OR/AND queries
from django.db.models import Q

premium_or_admin = User.objects.filter(
    Q(plan="premium") | Q(role="admin")
)

active_non_trial = User.objects.filter(
    Q(is_active=True) & ~Q(plan="trial")
)
```

---

### Q3: Custom Managers aur QuerySets kaise banate hain?
**Answer:**
```python
from django.db import models
from django.utils import timezone

class ActiveQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True, deleted_at__isnull=True)

    def by_user(self, user):
        return self.filter(user=user)

    def recent(self, days=30):
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(created_at__gte=cutoff)

class OrderQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(status="pending")

    def with_total(self):
        return self.annotate(item_count=Count("items"), total=Sum("items__price"))

class OrderManager(models.Manager):
    def get_queryset(self):
        return OrderQuerySet(self.model, using=self._db)

    def pending(self):
        return self.get_queryset().pending()

    def high_value(self, threshold=1000):
        return self.get_queryset().filter(amount__gte=threshold)

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50, default="pending")
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OrderManager()

# Usage:
Order.objects.pending()
Order.objects.high_value(500)
Order.objects.get_queryset().active().recent(7).with_total()
```

---

### Q4: Django ORM performance tips kya hain?
**Answer:**
```python
# 1. only() — sirf zaruri fields load karo
users = User.objects.only("id", "name", "email")

# 2. defer() — specific fields skip karo
users = User.objects.defer("bio", "profile_picture")  # heavy fields skip

# 3. values() / values_list() — dict/tuple return karo (no model instantiation)
emails = User.objects.values_list("email", flat=True)
user_data = User.objects.values("id", "name", "email")

# 4. iterator() — large querysets ke liye (cache nahi karta)
for user in User.objects.filter(is_active=True).iterator(chunk_size=500):
    process(user)

# 5. exists() — count() se fast (sirf EXISTS check)
if Order.objects.filter(user=user, status="pending").exists():
    print("Has pending orders")

# 6. bulk_create / bulk_update
users = [User(name=f"User{i}", email=f"u{i}@test.com") for i in range(1000)]
User.objects.bulk_create(users, batch_size=100)

User.objects.bulk_update(users, ["name", "email"], batch_size=100)

# 7. select_for_update — row level locking
with transaction.atomic():
    order = Order.objects.select_for_update().get(id=order_id)
    order.status = "processing"
    order.save()

# 8. EXPLAIN ANALYZE
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("EXPLAIN ANALYZE " + str(queryset.query))
    print(cursor.fetchall())
```

---

### Q5: Django signals kab aur kaise use karte hain?
**Answer:**
```python
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver

# post_save — user create hone ke baad profile banao
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

# pre_save — save se pehle kuch calculate karo
@receiver(pre_save, sender=Order)
def calculate_tax(sender, instance, **kwargs):
    if not instance.tax_amount:
        instance.tax_amount = instance.subtotal * 0.18

# post_delete — cleanup
@receiver(post_delete, sender=UserProfile)
def delete_profile_image(sender, instance, **kwargs):
    if instance.image:
        instance.image.delete(save=False)

# Custom signal
from django.dispatch import Signal

order_placed = Signal()  # custom signal

# Emit karo
order_placed.send(sender=Order, order=new_order, user=request.user)

# Listen karo
@receiver(order_placed)
def on_order_placed(sender, order, user, **kwargs):
    send_order_confirmation_email(user.email, order)
    update_inventory(order.items.all())
```

**Signal ka kab use karo:**
- Models ke beech loose coupling chahiye
- Third-party app extend karna ho
- Cross-cutting concerns (logging, notifications)

**Kab avoid karo:**
- Business logic tight coupling — service layer better hai
- Heavy operations — Celery use karo
