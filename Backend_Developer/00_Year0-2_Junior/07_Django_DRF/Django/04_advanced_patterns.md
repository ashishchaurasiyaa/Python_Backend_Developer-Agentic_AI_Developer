# Django — Advanced Patterns

## Topics
- Custom User Model (AbstractUser)
- Django Transactions (`atomic`, `select_for_update`, `on_commit`)
- Caching (cache_page, cache.set/get, cache invalidation)
- Admin customization

> DRF-side advanced patterns (django-filter/SearchFilter/OrderingFilter, nested serializer writes, `to_representation`, throttling) moved to [`../DRF/04_advanced_patterns.md`](../DRF/04_advanced_patterns.md).

---

## Interview Questions & Answers

### Q1: Custom User Model kaise banate hain? Kab banana chahiye?

**Answer:**
```python
# models.py
from django.contrib.auth.models import AbstractUser, BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra)

class User(AbstractUser):
    username = None        # remove username field
    email    = models.EmailField(unique=True)
    role     = models.CharField(max_length=20, default="user")
    plan     = models.CharField(max_length=20, default="free")

    USERNAME_FIELD  = "email"   # login se email use karo
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

# settings.py — FIRST migration se pehle set karo!
AUTH_USER_MODEL = "users.User"
```

**Kab banana chahiye:** ALWAYS — first migration se pehle hi set karo.
Baad mein change karna almost impossible hai (all FK references, migrations break).

---

### Q2: Django Transactions kaise kaam karte hain?

**Answer:**
```python
from django.db import transaction

# 1. transaction.atomic() — all or nothing
@transaction.atomic
def place_order(user_id, cart_items):
    order = Order.objects.create(user_id=user_id)
    for item in cart_items:
        OrderItem.objects.create(order=order, **item)
        Product.objects.filter(id=item["product_id"]).update(
            stock=F("stock") - item["quantity"]
        )
    # Exception hogi toh sab rollback

# 2. Savepoints (nested atomic)
def create_order_with_log(user, items):
    with transaction.atomic():
        order = Order.objects.create(user=user)
        try:
            with transaction.atomic():  # savepoint
                AuditLog.objects.create(action="order_created", user=user)
        except Exception:
            pass  # log fail ho toh order still saves
        # Main transaction continues

# 3. select_for_update — row-level lock (prevents race condition)
def transfer_credits(from_user_id, to_user_id, amount):
    with transaction.atomic():
        # Lock rows so no parallel transfer can read stale balance
        sender   = User.objects.select_for_update().get(id=from_user_id)
        receiver = User.objects.select_for_update().get(id=to_user_id)

        if sender.credits < amount:
            raise ValueError("Insufficient credits")

        sender.credits   -= amount
        receiver.credits += amount
        sender.save()
        receiver.save()

# 4. on_commit — run AFTER transaction commits
# INTERVIEW: Post_save signal mein Celery task send karo?
# Wrong: transaction rollback ho toh task still runs
# Correct: on_commit use karo
@receiver(post_save, sender=Order)
def send_confirmation(sender, instance, created, **kwargs):
    if created:
        transaction.on_commit(
            lambda: send_order_email.delay(instance.id)
        )
```

---

### Q3: Django Caching — cache_page vs cache.set/get?

**Answer:**
```python
# 1. cache_page — whole view response cache
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers

# Class-based view
@method_decorator(cache_page(60 * 5))           # 5 minutes
@method_decorator(vary_on_headers("Authorization"))  # per-user cache
def get(self, request, *args, **kwargs):
    ...

# 2. cache.set / cache.get — manual fine-grained cache
from django.core.cache import cache

def get_popular_posts():
    cache_key = "popular_posts_v1"
    posts = cache.get(cache_key)

    if posts is None:
        posts = list(
            Post.objects.published()
                .with_all_relations()
                .order_by("-views_count")[:10]
                .values()
        )
        cache.set(cache_key, posts, timeout=300)  # 5 minutes

    return posts

# 3. Cache invalidation — clear on update
def update_post(post_id, data):
    post = Post.objects.get(id=post_id)
    for k, v in data.items():
        setattr(post, k, v)
    post.save()

    # Invalidate related caches
    cache.delete(f"post_{post_id}")
    cache.delete("popular_posts_v1")
    cache.delete("featured_posts")

# 4. Cache versioning (better than delete)
from django.core.cache import cache

def get_user_feed(user_id):
    version = cache.get(f"user_feed_version:{user_id}", 1)
    cache_key = f"user_feed:{user_id}:v{version}"
    feed = cache.get(cache_key)
    if feed is None:
        feed = compute_feed(user_id)
        cache.set(cache_key, feed, timeout=600)
    return feed

def invalidate_user_feed(user_id):
    # Bump version — old key naturally expires
    cache.incr(f"user_feed_version:{user_id}", delta=1)

# settings.py
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
    }
}
```

---

### Q4: Django Admin — common customization patterns?

**Answer:**
```python
from django.contrib import admin

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    # List view
    list_display   = ["title", "author", "status", "views_count", "created_at"]
    list_filter    = ["status", "category"]
    search_fields  = ["title", "author__email"]
    ordering       = ["-created_at"]

    # Performance
    list_select_related = ["author", "category"]  # avoid N+1
    list_per_page = 50

    # Detail view
    readonly_fields     = ["created_at", "views_count"]
    filter_horizontal   = ["tags"]    # M2M with nice widget
    raw_id_fields       = ["author"]  # FK popup instead of dropdown (large tables)
    prepopulated_fields = {"slug": ("title",)}  # auto-fill slug

    # Custom action
    @admin.action(description="Publish selected posts")
    def publish(self, request, queryset):
        for post in queryset:
            post.publish()
        self.message_user(request, f"{queryset.count()} posts published.")

    actions = ["publish"]

    # Custom computed column
    @admin.display(description="Author Email", ordering="author__email")
    def author_email(self, obj):
        return obj.author.email

    # Override queryset for performance
    def get_queryset(self, request):
        return super().get_queryset(request).select_related("author", "category")
```
