# Custom Managers & QuerySets — Django Deep Dive

## Why It Matters (Senior 5 YOE Context)

Custom Managers aur QuerySets Django ka **most powerful but underused feature** hai. Production codebases mein 80% senior-level patterns inke bina possible nahi:

- **Soft-delete pattern** → `Model.objects.all()` deleted rows hide karta hai
- **Multi-tenant isolation** → har query mein tenant filter automatic
- **Chainable business filters** → `Order.objects.paid().recent().for_user(u)` readable code
- **DRY query logic** → same complex query 10 jagah copy-paste karne se bachta hai

Senior interviews mein common question: "How would you implement soft-delete site-wide?" — answer is Custom Manager + QuerySet.

---

## Core Concepts

### Level 1: Basic Manager Override

```python
from django.db import models

class PublishedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status='published')

class Article(models.Model):
    title = models.CharField(max_length=200)
    status = models.CharField(max_length=20)

    objects = models.Manager()      # default manager
    published = PublishedManager()  # custom manager

# Usage
Article.objects.all()       # sab articles
Article.published.all()     # sirf published
```

**Pitfall:** Pehla manager declared default banta hai. Agar `published` pehle declare karoge to admin/related queries mein bhi filter lagega.

### Level 2: Custom QuerySet (Chainable Methods)

QuerySet ka subclass banao taaki methods chain ho saken:

```python
class ArticleQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status='published')

    def by_author(self, user):
        return self.filter(author=user)

    def recent(self, days=7):
        from datetime import timedelta
        from django.utils import timezone
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)

class Article(models.Model):
    # ...
    objects = ArticleQuerySet.as_manager()

# Ab sab chainable hai
Article.objects.published().by_author(user).recent(30)
```

**Key insight:** `as_manager()` automatically QuerySet methods ko Manager mein expose kar deta hai.

### Level 3: Manager.from_queryset() — Best of Both Worlds

Jab tumhe Manager pe extra methods chahiye (jo QuerySet pe nahi) aur QuerySet pe chainable methods:

```python
class ArticleQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status='published')

    def by_author(self, user):
        return self.filter(author=user)


class ArticleManager(models.Manager):
    # Manager-only method (not chainable)
    def create_draft(self, title, author):
        return self.create(title=title, author=author, status='draft')


# Combine kar do
class Article(models.Model):
    objects = ArticleManager.from_queryset(ArticleQuerySet)()


# Ab dono available hain
Article.objects.create_draft("Hello", user)              # manager-only
Article.objects.published().by_author(user)              # chainable QS methods
Article.objects.filter(status='draft').by_author(user)   # filter + custom chain
```

### Level 4: Soft Delete Pattern (Production-Grade)

```python
class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        # Override bulk delete
        return super().update(deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        # Default queryset hides deleted
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class AllObjectsManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()       # hides deleted by default
    all_objects = AllObjectsManager()   # includes deleted

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        # Override instance delete too
        self.deleted_at = timezone.now()
        self.save(using=using)


# Usage
class Order(SoftDeleteModel):
    amount = models.DecimalField(max_digits=10, decimal_places=2)


Order.objects.all()        # only alive orders
Order.all_objects.all()    # alive + deleted
Order.all_objects.dead()   # only deleted
order.delete()             # sets deleted_at, doesn't DELETE
```

---

## How It Works Internally

### Manager Initialization Order

Django models me Manager assignment ka order matter karta hai:

1. **Default manager** = pehla declared manager (unless `default_manager_name` Meta mein set ho)
2. **`_meta.managers`** = sab managers ka tuple
3. **`_meta.base_manager`** = related queries (e.g., `user.orders.all()`) ke liye use hota hai

```python
class Order(models.Model):
    class Meta:
        default_manager_name = 'objects'    # explicit default
        base_manager_name = 'all_objects'   # related queries use this
```

**Why this matters:** Agar default manager `objects = SoftDeleteManager()` hai, to `user.orders.all()` deleted orders ko exclude karega — sometimes you want this, sometimes not.

### `as_manager()` Mechanics

```python
# Internally roughly equivalent to:
class ArticleQuerySet(models.QuerySet):
    def published(self): ...

# as_manager() basically does:
class _AutoManager(models.Manager):
    def get_queryset(self):
        return ArticleQuerySet(self.model, using=self._db)

    # auto-proxies methods from QuerySet
    published = ArticleQuerySet.published  # method promoted to manager
```

Django ka source: `django/db/models/manager.py:Manager._get_queryset_methods`.

### `from_queryset()` Internals

```python
# Django creates a new Manager subclass dynamically
NewManager = type(
    f'{Manager.__name__}From{QuerySet.__name__}',
    (Manager,),
    {**QuerySet_methods_promoted, '_queryset_class': QuerySet}
)
```

QuerySet methods Manager pe promote ho jaate hain via `__class_getitem__` magic.

---

## Common Pitfalls

### 1. Default Manager + Soft Delete Cascade Issue

```python
class Order(SoftDeleteModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')

# user.orders.all() — kya yeh deleted orders dikhayega?
# Depends on base_manager_name! Default hai 'objects' jo deleted hide karta hai.
# Result: cascade delete kabhi deleted orders ko touch nahi karega (data inconsistency)
```

**Fix:** Set `base_manager_name = 'all_objects'` for related queries to see everything.

### 2. Migrations Mein Custom Manager Use Nahi Kar Sakte

```python
# operations = [migrations.RunPython(my_func)]
# my_func ke andar Order.objects (custom manager) use hua to migration may fail
# Reason: historical model has no custom managers — use unmanaged manager
```

**Fix:** Migrations mein `apps.get_model('app', 'Order')._meta.default_manager` ya direct QuerySet use karo.

### 3. Manager Method vs QuerySet Method Confusion

```python
class ArticleManager(models.Manager):
    def published(self):
        return self.filter(status='published')

# This is Manager method — NOT chainable
Article.objects.published()                           # OK
Article.objects.filter(views__gt=100).published()     # ERROR — filter returns QuerySet, not Manager
```

**Fix:** Hamesha QuerySet pe method banao (via `QuerySet` subclass + `as_manager()`).

### 4. `get_queryset()` Override Cascade Issues

```python
class PublishedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status='published')

# Admin mein bhi sirf published dikhega — usually unwanted
# DRF mein router ke saath bhi yeh behavior leak hota hai
```

**Fix:** Use named manager (`published = PublishedManager()`), keep `objects = models.Manager()` as default.

### 5. `select_related` / `prefetch_related` with Custom Manager

```python
# Custom manager ke andar select_related lagao — perf gain har query mein
class ArticleQuerySet(models.QuerySet):
    def with_author(self):
        return self.select_related('author').prefetch_related('tags')

Article.objects.published().with_author()  # JOINs included
```

### 6. Manager `_db` Multi-DB Handling

Custom manager mein `using(db_alias)` chain hone ke liye `self._db` ko respect karna zaroori hai:

```python
class MyManager(models.Manager):
    def get_queryset(self):
        return MyQuerySet(self.model, using=self._db)  # critical for multi-DB
```

---

## Interview Q&A

**Q1:** Difference between Manager and QuerySet?
**A:** Manager is the entry point to query the database (`Model.objects`), returns QuerySets. QuerySet is the actual lazy-evaluated query that's chainable. Custom QuerySets give chainability; custom Managers give methods that operate on the model (like `create_draft()`).

**Q2:** Soft delete kaise implement karoge site-wide?
**A:** Abstract base model with `deleted_at` field + custom QuerySet that overrides `delete()` (sets timestamp) + custom Manager whose `get_queryset()` filters `deleted_at__isnull=True`. Also `all_objects` manager for admin/audit access. Override instance `.delete()` too. Set `base_manager_name = 'all_objects'` to avoid cascade bugs.

**Q3:** `as_manager()` vs `from_queryset()`?
**A:** `as_manager()` shortcut — promote QuerySet methods to a default Manager. `from_queryset()` jab Manager pe alag methods bhi chahiye (jo QuerySet pe nahi banane). `from_queryset()` is more flexible — preserves both Manager-only + QuerySet-chain methods.

**Q4:** Default manager kya hota hai aur kab matter karta hai?
**A:** Class mein declared pehla Manager = `_default_manager`. Yeh dumping/loading, related queries, generic relations sab use karte hain. Agar pehla manager filter karta hai (e.g., `PublishedManager`), to `dumpdata` se published rows ही export honge — usually unwanted. Always keep `objects = models.Manager()` first.

**Q5:** Multi-tenant queries kaise enforce karoge via Manager?
**A:** ThreadLocal/`contextvars` se current tenant capture karo (middleware mein set), Manager `get_queryset()` mein `filter(tenant_id=current_tenant_id())`. But row-level security in DB is safer (PostgreSQL RLS). Manager approach = app-level enforcement, can be bypassed via raw SQL.

**Q6:** Manager method `create_draft()` likhna chahiye ya QuerySet pe?
**A:** Manager pe — kyunki yeh "model-level" operation hai (create new row), not "query existing rows". Rule of thumb: agar method `self.filter().xyz()` chain expect karta hai = QuerySet method. Agar standalone create/operation hai = Manager method.

**Q7:** Custom Manager ke saath related lookups (`user.orders`) ka behavior kya hota hai?
**A:** Django `_base_manager` use karta hai (default = first declared manager). Agar tumhara default `SoftDeleteManager` hai, to `user.orders.all()` deleted orders ko exclude karega — cascade delete bhi affect ho sakta hai. Fix: `Meta.base_manager_name = 'all_objects'`.

**Q8:** Migrations mein custom manager use kar sakte ho?
**A:** Nahi (directly). Historical models (`apps.get_model()`) custom managers/methods nahi rakhte — sirf fields. Use `_default_manager` ya raw QuerySet operations (`filter`, `update`, etc.).

---

## Real-World Use Cases

### 1. E-commerce Order Lifecycle

```python
class OrderQuerySet(models.QuerySet):
    def paid(self):
        return self.filter(status='paid')

    def pending(self):
        return self.filter(status='pending')

    def refundable(self):
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=30)
        return self.paid().filter(paid_at__gte=cutoff)

    def for_user(self, user):
        return self.filter(user=user)


# Reporting query super readable
Order.objects.paid().for_user(user).refundable().count()
```

### 2. Multi-Tenant SaaS

```python
from contextvars import ContextVar

current_tenant_id: ContextVar[int] = ContextVar('current_tenant_id', default=None)


class TenantManager(models.Manager):
    def get_queryset(self):
        qs = super().get_queryset()
        tenant_id = current_tenant_id.get()
        if tenant_id is None:
            raise RuntimeError("Tenant context not set")
        return qs.filter(tenant_id=tenant_id)


class Project(models.Model):
    tenant_id = models.IntegerField(db_index=True)
    objects = TenantManager()
    all_tenants = models.Manager()  # admin only
```

### 3. Audit Trail (Polymorphic Activity Log)

```python
class ActivityQuerySet(models.QuerySet):
    def for_object(self, obj):
        ct = ContentType.objects.get_for_model(obj)
        return self.filter(content_type=ct, object_id=obj.pk)

    def recent(self, hours=24):
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(created_at__gte=cutoff)


# Usage
Activity.objects.for_object(order).recent(48)
```

---

## References

- [Django docs — Managers](https://docs.djangoproject.com/en/5.0/topics/db/managers/)
- [Django docs — QuerySet API](https://docs.djangoproject.com/en/5.0/ref/models/querysets/)
- Django source: `django/db/models/manager.py`
- Two Scoops of Django — Chapter on Managers + QuerySets
- Real-world soft delete: `django-safedelete` library source code
