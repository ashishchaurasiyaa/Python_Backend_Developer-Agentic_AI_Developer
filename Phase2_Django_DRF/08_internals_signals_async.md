# Django Internals, Signals & Async — Deep Dive

## Quick Concepts
- **Request/Response Lifecycle** = Browser se response tak ka poora safar — middleware stack, URL resolver, view, back
- **Signals** = Observer pattern — kuch event hone pe automatically doosra code trigger karo (loose coupling)
- **Async Django** = `async def` views + await — blocking I/O se bachao, throughput badhao
- **DRF Internals** = `dispatch()` → `initial()` → authentication → permissions → throttling → view method

---

## Section A — Django Request/Response Lifecycle

### What hai ye?
Jab browser ek HTTP request bhejta hai, toh Django us request ko ek assembly line ki tarah process karta hai. Har step mein kuch kaam hota hai — middleware stack se lekar view execution tak aur wapas response.

### Why samajhna zaroori hai?
- Debugging ke waqt samajh aata hai ki error kahan aa rahi hai
- Custom middleware likhne ke liye lifecycle samajhna padta hai
- Performance optimization ke liye jaanna chahiye ki request kahan time spend karti hai
- Security middleware (CSRF, auth) kaise kaam karta hai ye samajh aata hai

### How — Complete Flow:

```
Browser HTTP Request
        ↓
WSGI/ASGI Server (Gunicorn / Uvicorn)
        ↓
Django Application Bootstrap
  - settings.py load hoti hai
  - INSTALLED_APPS ke liye AppConfig instantiate hote hain
  - AppConfig.ready() methods call hote hain
        ↓
Middleware Stack — process_request (TOP se BOTTOM)
  - SecurityMiddleware
  - SessionMiddleware
  - CommonMiddleware
  - CsrfViewMiddleware
  - AuthenticationMiddleware   ← request.user set hota hai yahan
  - MessageMiddleware
  - XFrameOptionsMiddleware
  - [Aapka custom middleware]
        ↓
URL Resolver
  - urlpatterns match karta hai
  - View function/class dhundta hai
  - URL parameters extract karta hai
        ↓
View Execute (FBV ya CBV)
  - Business logic chalti hai
  - Response object banta hai
        ↓
Middleware Stack — process_response (BOTTOM se TOP, reverse order)
        ↓
WSGI/ASGI — response bytes browser ko bhejta hai
        ↓
Browser Response Receive Karta Hai
```

### WSGI vs ASGI — Fark kya hai?

```
WSGI (Web Server Gateway Interface):
- Synchronous / blocking
- Ek request → ek thread block hoti hai jab tak response nahi milta
- Gunicorn workers use karte hain WSGI ke liye
- Django 1.x se traditional approach
- CPU-bound ya simple apps ke liye theek hai

ASGI (Asynchronous Server Gateway Interface):
- Asynchronous / non-blocking
- Event loop pe based — ek thread many requests handle kar sakta hai
- Uvicorn / Daphne use karte hain ASGI ke liye
- WebSockets, Server-Sent Events support karta hai (WSGI nahi kar sakta)
- Django Channels bhi ASGI pe hi kaam karta hai
- I/O-bound operations ke liye bahut better (DB calls, external APIs)
```

```python
# settings.py mein switch karna easy hai:

# WSGI (default, sync):
WSGI_APPLICATION = 'myproject.wsgi.application'

# ASGI (async support):
ASGI_APPLICATION = 'myproject.asgi.application'

# myproject/asgi.py
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
application = get_asgi_application()
```

### AppConfig aur ready() — App Loading Kaise Hoti Hai

```python
# users/apps.py
from django.apps import AppConfig

class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
    verbose_name = 'User Management'

    def ready(self):
        """
        Ye method ek baar call hota hai jab Django poora load ho jaata hai.
        Yahan karo:
        1. Signals register karo (MOST COMMON USE CASE)
        2. Periodic tasks schedule karo
        3. External service connections verify karo
        
        Yahan MAT karo:
        - Database queries (DB abhi ready nahi ho sakta)
        - Heavy initialization (startup slow ho jaayega)
        """
        import users.signals  # signals ko register karo
        
        # Ya explicitly:
        from django.db.models.signals import post_save
        from users.signals import create_user_profile
        from django.contrib.auth import get_user_model
        User = get_user_model()
        post_save.connect(create_user_profile, sender=User)

# settings.py mein:
INSTALLED_APPS = [
    'users.apps.UsersConfig',  # Sirf 'users' likhne se bhi kaam karta hai
    # ...
]
```

### Custom Middleware — Request Lifecycle Trace Karo

```python
# myproject/middleware.py

import time
import logging

logger = logging.getLogger(__name__)


class RequestLifecycleMiddleware:
    """
    Har request ka time track karo aur log karo.
    
    Middleware ek callable hai jo:
    - __init__: ek baar app startup pe call hota hai
    - __call__: har request pe call hota hai
    """
    
    def __init__(self, get_response):
        """
        One-time configuration — app startup pe.
        get_response = next middleware ya actual view
        """
        self.get_response = get_response
        logger.info("RequestLifecycleMiddleware initialized — app startup pe ek baar")

    def __call__(self, request):
        # ═══ BEFORE VIEW ═══
        start_time = time.monotonic()
        request._start_time = start_time
        
        logger.info(
            f"→ REQUEST START | {request.method} {request.path} "
            f"| User: {getattr(request, 'user', 'anonymous')} "
            f"| IP: {self.get_client_ip(request)}"
        )

        # Ye call karne se:
        # 1. Neeche ke saare middlewares chalte hain
        # 2. Phir actual view chalti hai
        # 3. Phir upar ke middlewares ka process_response hota hai
        response = self.get_response(request)

        # ═══ AFTER VIEW ═══
        duration_ms = (time.monotonic() - start_time) * 1000
        
        logger.info(
            f"← RESPONSE END | {response.status_code} "
            f"| {duration_ms:.2f}ms | {request.path}"
        )
        
        # Custom header add karo response mein
        response['X-Process-Time'] = f"{duration_ms:.2f}ms"
        response['X-Request-ID'] = getattr(request, '_request_id', 'unknown')
        
        return response

    def process_exception(self, request, exception):
        """
        View mein exception aane pe Django ye method call karta hai.
        Return None = Django default exception handling chalti hai
        Return HttpResponse = custom error response
        """
        logger.error(
            f"EXCEPTION in {request.method} {request.path}: "
            f"{type(exception).__name__}: {exception}",
            exc_info=True
        )
        return None  # Django ko default handling karne do

    @staticmethod
    def get_client_ip(request):
        """Real IP dhundho — proxy ke peeche bhi"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


# settings.py mein register karo:
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'myproject.middleware.RequestLifecycleMiddleware',  # Yahan add karo
    'django.contrib.sessions.middleware.SessionMiddleware',
    # ...
]
```

---

## Section B — Django Signals

### What hain Signals?
Signals ek **Observer Pattern** implementation hai Django mein. Jab koi specific event hota hai (jaise user save hona), toh aap registered listeners (receivers) ko automatically notify kar sakte ho — bina direct function call ke.

### Why use karte hain?
- **Loose coupling**: `User` model ko `Profile` ya `Email` ke baare mein kuch nahi pata hona chahiye — signal ke through kaam hota hai
- **Reusability**: Ek signal pe multiple receivers hook kar sakte ho
- **Separation of concerns**: User creation logic `users/` mein, email sending logic `notifications/` mein — dono alag rahe

### Built-in Django Signals:

```python
# Models ke signals
from django.db.models.signals import (
    pre_save,    # .save() se PEHLE — data validate/modify kar sakte ho
    post_save,   # .save() ke BAAD — side effects ke liye (profile create, etc.)
    pre_delete,  # .delete() se PEHLE — cleanup ya audit log
    post_delete, # .delete() ke BAAD — cleanup complete
    m2m_changed, # ManyToMany field badalne pe (add/remove/clear)
    pre_init,    # Model __init__ se pehle
    post_init,   # Model __init__ ke baad
)

# Request signals
from django.core.signals import (
    request_started,   # Har HTTP request shuru pe
    request_finished,  # Har HTTP request khatam pe
    got_request_exception,  # Unhandled exception pe
)

# Database signals
from django.db.backends.signals import connection_created

# Management command signals
from django.test.signals import setting_changed  # Test mein settings change pe
```

### @receiver Decorator — Signal Register Karo

```python
# users/signals.py

from django.db.models.signals import post_save, pre_delete, m2m_changed
from django.dispatch import receiver, Signal
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


# ─── 1. post_save — Profile auto-create ───────────────────────────────────────

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    sender   = User class
    instance = actual User object jo save hua
    created  = True agar naya user, False agar update
    **kwargs = raw, update_fields, etc.
    """
    if created:
        # Circular import avoid karo — local import use karo
        from users.models import Profile
        Profile.objects.create(user=instance)
        print(f"Profile created for: {instance.email}")


# ─── 2. post_save — Welcome Email with Celery ─────────────────────────────────

@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs):
    """
    Signal se directly email mat bhejo — Celery task queue karo.
    Kyun? Signal synchronous hota hai — email bhejne mein time lagta hai,
    request slow ho jaayegi.
    """
    if created:
        # Celery task import karo aur queue mein daalo
        from notifications.tasks import send_welcome_email_task
        send_welcome_email_task.delay(
            user_id=instance.id,
            email=instance.email,
            name=instance.get_full_name() or instance.username,
        )
        # .delay() return hote hi function khatam — non-blocking!


# ─── 3. pre_delete — Audit Log ────────────────────────────────────────────────

@receiver(pre_delete, sender=User)
def log_user_deletion(sender, instance, **kwargs):
    """
    pre_delete use karo kyunki:
    - Object still exists in DB (ID, data sab available hai)
    - post_delete mein related objects already delete ho chuke hote hain
    """
    from audit.models import AuditLog
    AuditLog.objects.create(
        action="USER_DELETED",
        object_id=instance.id,
        object_repr=f"User: {instance.email} (ID: {instance.id})",
        extra_data={
            "username": instance.username,
            "email": instance.email,
            "date_joined": instance.date_joined.isoformat(),
            "is_staff": instance.is_staff,
        },
        timestamp=timezone.now(),
    )


# ─── 4. m2m_changed — Groups Change Track Karo ───────────────────────────────

@receiver(m2m_changed, sender=User.groups.through)
def on_user_groups_changed(sender, instance, action, pk_set, model, **kwargs):
    """
    action values:
    - "pre_add"    — add hone se pehle
    - "post_add"   — add hone ke baad   ← most useful
    - "pre_remove" — remove hone se pehle
    - "post_remove"— remove hone ke baad
    - "pre_clear"  — clear hone se pehle
    - "post_clear" — clear hone ke baad
    
    pk_set = set of PKs jo add/remove hue
    instance = User object
    """
    if action == "post_add":
        from django.contrib.auth.models import Group
        group_names = Group.objects.filter(pk__in=pk_set).values_list('name', flat=True)
        print(f"User '{instance.email}' added to groups: {list(group_names)}")
    
    elif action == "post_remove":
        print(f"User '{instance.email}' removed from groups: {pk_set}")
```

### Custom Signals — Apna Signal Banao

```python
# payments/signals.py

from django.dispatch import Signal

# Signal define karo — providing_args sirf documentation ke liye (Python 3.x mein enforce nahi hota)
payment_completed = Signal()  # sends: user, amount, order_id, currency
payment_failed = Signal()     # sends: user, amount, order_id, error_message
refund_initiated = Signal()   # sends: user, amount, order_id, reason


# Signal send karo (sender class ya None ho sakta hai)
def process_payment(user, amount, order_id, currency="INR"):
    try:
        # ... actual payment gateway logic ...
        result = call_payment_gateway(amount, order_id)
        
        if result.success:
            # Sabko notify karo ki payment complete hua
            payment_completed.send(
                sender=None,  # Ya sender=PaymentProcessor
                user=user,
                amount=amount,
                order_id=order_id,
                currency=currency,
                transaction_id=result.transaction_id,
            )
            return result
        else:
            payment_failed.send(
                sender=None,
                user=user,
                amount=amount,
                order_id=order_id,
                error_message=result.error,
            )
    except Exception as e:
        payment_failed.send(sender=None, user=user, amount=amount, 
                           order_id=order_id, error_message=str(e))
        raise


# Signal receivers — alag apps mein register karo
@receiver(payment_completed)
def update_order_status(sender, user, amount, order_id, **kwargs):
    """Order ko paid mark karo"""
    from orders.models import Order
    Order.objects.filter(id=order_id).update(
        status='paid',
        paid_at=timezone.now(),
        amount_paid=amount,
    )


@receiver(payment_completed)
def send_payment_receipt(sender, user, amount, order_id, **kwargs):
    """Receipt email bhejo"""
    from notifications.tasks import send_receipt_email_task
    send_receipt_email_task.delay(
        user_id=user.id,
        amount=str(amount),
        order_id=order_id,
    )


@receiver(payment_completed)
def update_analytics(sender, user, amount, order_id, currency, **kwargs):
    """Analytics update karo — Revenue tracking"""
    from analytics.models import RevenueEvent
    RevenueEvent.objects.create(
        user=user,
        amount=amount,
        currency=currency,
        order_id=order_id,
    )
```

### Tests Mein Signals Disconnect Karna — Bahut Important!

```python
# tests/test_users.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from unittest.mock import patch

User = get_user_model()


class UserCreationTest(TestCase):
    
    def test_user_creation_without_signals(self):
        """
        Test mein signals disconnect karo nahi toh:
        - Profile create hoga (extra DB hit)
        - Email task queue hoga (Celery/Redis chahiye)
        - Test slow ya fail ho sakta hai
        """
        from users.signals import create_user_profile, send_welcome_email
        
        # Disconnect karo
        post_save.disconnect(create_user_profile, sender=User)
        post_save.disconnect(send_welcome_email, sender=User)
        
        try:
            user = User.objects.create_user(
                username='testuser',
                email='test@example.com',
                password='testpass123'
            )
            self.assertEqual(user.email, 'test@example.com')
        finally:
            # HAMESHA reconnect karo — finally block mein
            post_save.connect(create_user_profile, sender=User)
            post_save.connect(send_welcome_email, sender=User)
    
    def test_with_mock_patch(self):
        """
        Aur bhi clean approach — mock.patch use karo
        """
        with patch('users.signals.send_welcome_email') as mock_signal:
            user = User.objects.create_user(username='u2', email='u2@example.com')
            # Signal fire hua par actual function mock tha
        
    @classmethod
    def setUpClass(cls):
        """
        Poore TestCase ke liye ek baar disconnect karo
        """
        super().setUpClass()
        post_save.disconnect(sender=User)  # ALL receivers disconnect
    
    @classmethod
    def tearDownClass(cls):
        """Reconnect karo"""
        super().tearDownClass()
        # Re-import signals to re-register
        import users.signals  # noqa


# Clean approach — factory_boy ya pytest-django signal mocking use karo:

# pytest-django approach:
# @pytest.mark.django_db
# def test_user(django_db_blocker):
#     with mock.patch('users.signals.create_user_profile'):
#         user = User.objects.create_user(...)
```

### Signals vs Celery Tasks — Kab Kya Use Karo?

```
SIGNALS use karo jab:
✅ Synchronous side effects chahiye (Profile create, Audit log)
✅ Same process mein kaam hona chahiye
✅ Simple aur fast operations (DB write, in-memory update)
✅ Loose coupling chahiye same service ke andar

CELERY TASKS use karo jab:
✅ Email/SMS bhejni ho (external I/O)
✅ Slow operations (image processing, PDF generate)
✅ Retry logic chahiye (API calls fail ho sakti hain)
✅ Scheduled/delayed execution chahiye
✅ Heavy computation

COMBINED approach (best practice):
Signal → Celery Task queue → Background execution
  (fast)      (async)            (reliable)
```

### Interview Q: Circular Import Signals Mein Kaise Avoid Karo?

```python
# PROBLEM — ye circular import create karta hai:

# users/models.py
from notifications.models import Notification  # ← notification import karta hai users se
class User(AbstractUser):
    pass

# notifications/models.py  
from users.models import User  # ← users import karta hai notifications se
class Notification(models.Model):
    user = models.ForeignKey(User, ...)

# Ab agar users/signals.py mein ye likho:
# from notifications.models import Notification  # CIRCULAR!


# SOLUTION 1 — Local imports in signal functions:
@receiver(post_save, sender=User)
def create_notification(sender, instance, created, **kwargs):
    if created:
        from notifications.models import Notification  # ← local import
        Notification.objects.create(user=instance, message="Welcome!")


# SOLUTION 2 — get_user_model() use karo models mein:
# notifications/models.py
from django.contrib.auth import get_user_model
# User = get_user_model()  # ← TOP pe mat karo

class Notification(models.Model):
    user = models.ForeignKey(
        'auth.User',  # String reference use karo
        on_delete=models.CASCADE
    )
    # Ya:
    user = models.ForeignKey(
        'users.User',  # App label.ModelName string
        on_delete=models.CASCADE
    )


# SOLUTION 3 — Signals apps.ready() mein register karo:
# users/apps.py
class UsersConfig(AppConfig):
    name = 'users'
    
    def ready(self):
        # Yahan import karo — by this time all apps are loaded
        import users.signals  # noqa — side effects: signal registration
        # Ab koi circular import nahi kyunki dono apps fully loaded hain
```

---

## Section C — Async Django

### What hai Async Django?
Django 3.1 se async views support aaya. `async def` keyword se view define karo aur I/O operations `await` karo — thread block nahi hogi, server zyada requests handle kar payega.

### Why use karo?
- Traditional sync view mein: 1 request = 1 thread blocked (DB response ka wait)
- Async view mein: 1 thread = many concurrent requests handle kar sakta hai
- External API calls, database operations — sab concurrently ho sakte hain

### How — Async Views Likhna:

```python
# views.py

import asyncio
import httpx
from django.http import JsonResponse
from asgiref.sync import sync_to_async, async_to_sync
from django.contrib.auth import get_user_model

User = get_user_model()


# ─── Basic Async View ─────────────────────────────────────────────────────────

async def async_hello(request):
    """Simplest async view"""
    return JsonResponse({"message": "Hello from async view!"})


# ─── Django 4.1+ Async ORM ────────────────────────────────────────────────────

async def async_user_count(request):
    """
    Django 4.1+ mein ORM ke async methods available hain:
    aget(), afilter(), acount(), acreate(), aupdate(), adelete(), aexists()
    """
    # aget() — single object fetch
    # acount() — count
    # afilter() — filter (QuerySet return karta hai, iterate ke liye async for)
    
    count = await User.objects.filter(is_active=True).acount()
    
    # Ek object fetch karo
    try:
        user = await User.objects.aget(id=1)
        username = user.username
    except User.DoesNotExist:
        username = None
    
    # Create karo
    # new_user = await User.objects.acreate(username='async_user', email='a@b.com')
    
    return JsonResponse({"active_users": count, "first_user": username})


# ─── sync_to_async — Older Code Wrap Karo ────────────────────────────────────

async def async_product_view(request, product_id):
    """
    Purani code ya third-party libraries jo async support nahi karti
    unhe sync_to_async se wrap karo
    """
    from products.models import Product
    
    # METHOD 1 — lambda/callable wrap karo
    get_product = sync_to_async(Product.objects.get)
    
    try:
        product = await get_product(id=product_id)
    except Product.DoesNotExist:
        return JsonResponse({"error": "Product not found"}, status=404)
    
    # METHOD 2 — decorator style
    @sync_to_async
    def get_related_products():
        # Yahan sync ORM queries likh sakte ho freely
        return list(
            Product.objects.filter(
                category=product.category
            ).exclude(id=product_id)[:5].values('id', 'name', 'price')
        )
    
    related = await get_related_products()
    
    return JsonResponse({
        "name": product.name,
        "price": str(product.price),
        "related": related,
    })


# ─── Concurrent Operations — asyncio.gather ──────────────────────────────────

async def dashboard_view(request):
    """
    Multiple independent DB calls parallel mein karo.
    Sequential: 3 queries × 100ms each = 300ms total
    Parallel:   3 queries simultaneously = ~100ms total
    """
    from products.models import Product
    from orders.models import Order
    
    # Ye sab PARALLEL chalenge — asyncio.gather magic!
    user_count, product_count, pending_orders = await asyncio.gather(
        User.objects.filter(is_active=True).acount(),
        Product.objects.filter(is_available=True).acount(),
        Order.objects.filter(status='pending').acount(),
    )
    
    return JsonResponse({
        "active_users": user_count,
        "available_products": product_count,
        "pending_orders": pending_orders,
    })


# ─── External API Call — httpx.AsyncClient ───────────────────────────────────

async def weather_view(request, city: str):
    """
    External API calls ke liye httpx use karo (requests library async nahi hai).
    httpx.AsyncClient non-blocking HTTP requests karta hai.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"https://api.openweathermap.org/data/2.5/weather",
                params={
                    "q": city,
                    "appid": "your_api_key",
                    "units": "metric",
                },
            )
            response.raise_for_status()
            data = response.json()
            return JsonResponse({
                "city": city,
                "temp": data["main"]["temp"],
                "description": data["weather"][0]["description"],
            })
        except httpx.TimeoutException:
            return JsonResponse({"error": "Weather API timeout"}, status=504)
        except httpx.HTTPStatusError as e:
            return JsonResponse({"error": str(e)}, status=502)


# ─── Multiple External APIs — Truly Parallel ─────────────────────────────────

async def product_enriched_view(request, product_id):
    """
    Product info + reviews + inventory sab ek saath fetch karo
    """
    from products.models import Product
    
    product = await Product.objects.aget(id=product_id)
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        # Ye dono API calls PARALLEL chalenge
        reviews_resp, inventory_resp = await asyncio.gather(
            client.get(f"https://reviews-api.example.com/products/{product_id}"),
            client.get(f"https://inventory-api.example.com/stock/{product_id}"),
            return_exceptions=True,  # Ek fail hone pe doosra cancel na ho
        )
    
    reviews = reviews_resp.json() if not isinstance(reviews_resp, Exception) else []
    inventory = inventory_resp.json() if not isinstance(inventory_resp, Exception) else {}
    
    return JsonResponse({
        "product": {"id": product.id, "name": product.name},
        "reviews": reviews,
        "inventory": inventory,
    })
```

### CRITICAL — SynchronousOnlyOperation Exception

```python
# ❌ GALAT — ye Django < 4.1 mein SynchronousOnlyOperation raise karega:

async def bad_view(request):
    # Direct ORM call async context mein — CRASH!
    users = list(User.objects.all())  # SynchronousOnlyOperation!
    
    # Ye bhi galat:
    user = User.objects.get(id=1)  # SynchronousOnlyOperation!
    
    return JsonResponse({"count": len(users)})


# ✅ SAHI — sync_to_async wrapper use karo (Django < 4.1):

async def good_view_old_style(request):
    # Option 1 — sync_to_async se wrap karo
    get_users = sync_to_async(lambda: list(User.objects.all()))
    users = await get_users()
    
    # Option 2 — thread_sensitive=False for non-ORM operations
    # ORM operations: thread_sensitive=True (default) rakho
    # Non-ORM: thread_sensitive=False se performance better hoti hai
    run_in_thread = sync_to_async(some_sync_function, thread_sensitive=False)
    result = await run_in_thread()
    
    return JsonResponse({"count": len(users)})


# ✅ SAHI — Django 4.1+ async ORM:

async def good_view_new_style(request):
    # Native async ORM methods
    users = await sync_to_async(list)(
        User.objects.filter(is_active=True).select_related('profile')
    )
    # Ya:
    count = await User.objects.filter(is_active=True).acount()
    
    return JsonResponse({"count": count})
```

### Async Middleware

```python
# middleware.py

import time
from django.utils.decorators import sync_and_async_middleware


class AsyncCapableMiddleware:
    """
    Ye middleware async aur sync dono views ke saath kaam karta hai.
    Django automatically detect karta hai ki view sync hai ya async.
    """
    
    async_capable = True
    sync_capable = True
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Check: kya get_response async hai?
        if asyncio.iscoroutinefunction(self.get_response):
            self._is_coroutine = asyncio.coroutines._is_coroutine
    
    def __call__(self, request):
        """Sync version"""
        if asyncio.iscoroutinefunction(self.get_response):
            return self.__acall__(request)
        
        start = time.monotonic()
        response = self.get_response(request)
        duration = (time.monotonic() - start) * 1000
        response['X-Process-Time'] = f"{duration:.2f}ms"
        return response
    
    async def __acall__(self, request):
        """Async version"""
        start = time.monotonic()
        response = await self.get_response(request)
        duration = (time.monotonic() - start) * 1000
        response['X-Process-Time'] = f"{duration:.2f}ms"
        return response
```

### Async Django vs FastAPI — Kab Kya Chunno?

```
Django Async use karo jab:
✅ Existing Django project mein async add karna hai
✅ Django ORM, Admin, Auth, Signals — sab chahiye
✅ Team Django se familiar hai
✅ Complex business logic, multiple Django apps
✅ Gradually migrate karna hai sync se async

FastAPI use karo jab:
✅ Greenfield project — pure async API
✅ Automatic OpenAPI/Swagger docs chahiye built-in
✅ Maximum performance chahiye (pure async app)
✅ Simple microservice banana hai
✅ Pydantic validation heavy use karna hai
✅ Team Python type hints se comfortable hai
```

---

## Section D — DRF Internals

### What hai DRF Internals?
DRF (Django REST Framework) ke andar request processing ka poora flow — Django ke raw request se lekar JSON response tak kaise pohnchta hai.

### Why jaanna chahiye?
- Custom authentication likhne ke liye
- Custom permissions implement karne ke liye
- Debugging karna aasaan hota hai
- Advanced customization possible hoti hai

### How — DRF Dispatch Flow:

```
Client HTTP Request
        ↓
Django URLResolver → View.as_view()
        ↓
APIView.dispatch(request, *args, **kwargs)
        ├── initialize_request()
        │     └── Django HttpRequest → DRF Request wrap karo
        │         - request.auth
        │         - request.authenticators = [auth1, auth2, ...]
        │         - request.parsers = [JSONParser, MultiPartParser, ...]
        │         - request.negotiator
        │
        ├── initial(request, *args, **kwargs)
        │     ├── perform_authentication(request)
        │     │     └── request.user access → _authenticate() call
        │     │         → authenticators iterate → first success wins
        │     │
        │     ├── check_permissions(request)
        │     │     └── har permission.has_permission() call
        │     │         → False mile toh 403 Forbidden
        │     │
        │     └── check_throttles(request)
        │           └── har throttle.allow_request() call
        │               → False mile toh 429 Too Many Requests
        │
        └── View Method (get/post/put/patch/delete)
              └── Response object return karo
```

### DRF Request — Django Request se Alag Kaise?

```python
# DRF Request wrapper kya add karta hai?

# Django Request:
request.POST        # Form data
request.GET         # Query params
request.META        # Headers
request.user        # Authenticated user (Django auth)
request.body        # Raw bytes

# DRF Request (oopar Django Request wrap hota hai):
request.data        # Parsed body (JSON, multipart, etc.) — request.POST ka replacement
request.query_params # Same as request.GET but more readable
request.user        # Lazy property — pehle access pe authentication trigger hoti hai
request.auth        # Authentication object (token, etc.)
request.authenticators  # List of authenticator instances
request.accepted_renderer  # Content negotiation se decide hua renderer
request._request    # Original Django request access

# Ye kyun better hai?
# Content-Type ke hisaab se data parse karta hai:
# Content-Type: application/json  → request.data mein dict milega
# Content-Type: multipart/form-data → request.data mein QueryDict milega
```

### ViewSet → Router → URLs — Kaise Kaam Karta Hai?

```python
# viewsets.py
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response


class ProductViewSet(viewsets.ModelViewSet):
    """
    ModelViewSet in actions automatically provide karta hai:
    list()    → GET  /products/
    create()  → POST /products/
    retrieve()→ GET  /products/{pk}/
    update()  → PUT  /products/{pk}/
    partial_update() → PATCH /products/{pk}/
    destroy() → DELETE /products/{pk}/
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    
    # Custom action add karo
    @action(detail=True, methods=['post'], url_path='add-to-cart')
    def add_to_cart(self, request, pk=None):
        """
        URL: POST /products/{pk}/add-to-cart/
        detail=True  → specific object ke liye (pk chahiye)
        detail=False → collection-level action
        """
        product = self.get_object()
        # cart logic...
        return Response({"message": f"{product.name} added to cart"})
    
    @action(detail=False, methods=['get'], url_path='featured')
    def featured(self, request):
        """
        URL: GET /products/featured/
        """
        featured = Product.objects.filter(is_featured=True)
        serializer = self.get_serializer(featured, many=True)
        return Response(serializer.data)


# urls.py — Router magic
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register('products', ProductViewSet, basename='product')

# Router automatically ye URLs banata hai:
# GET    /products/           → list
# POST   /products/           → create
# GET    /products/{pk}/      → retrieve
# PUT    /products/{pk}/      → update
# PATCH  /products/{pk}/      → partial_update
# DELETE /products/{pk}/      → destroy
# POST   /products/{pk}/add-to-cart/ → add_to_cart (custom action)
# GET    /products/featured/  → featured (custom action)

urlpatterns = [
    path('api/', include(router.urls)),
]
```

### Serializer Internals — to_internal_value vs to_representation

```python
# serializers.py

from rest_framework import serializers
from decimal import Decimal


class ProductSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'category', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def to_internal_value(self, data):
        """
        INPUT SIDE — Request body → Python dict (validated)
        
        Ye tab call hota hai jab serializer.is_valid() call karo.
        Raw dict → validated Python types.
        
        Order:
        1. to_internal_value() call hota hai
        2. validate_<field>() methods call hote hain (field-level)
        3. validate() call hota hai (object-level)
        4. Result: self.validated_data mein milta hai
        """
        print(f"[to_internal_value] Raw input received: {data}")
        # Pehle parent ka kaam karne do
        value = super().to_internal_value(data)
        print(f"[to_internal_value] After parent processing: {value}")
        return value
    
    def to_representation(self, instance):
        """
        OUTPUT SIDE — DB object → dict (serialized for JSON response)
        
        Ye tab call hota hai jab response mein data serialize karo.
        Model instance → dict → JSON.
        
        Yahan:
        - Fields hide karo based on user permission
        - Computed fields add karo
        - Nested data format karo
        """
        print(f"[to_representation] Serializing: {instance}")
        result = super().to_representation(instance)
        
        # Computed field add karo
        result['formatted_price'] = f"₹{result['price']}"
        result['is_expensive'] = Decimal(result['price']) > 1000
        
        # Request context available hai yahan bhi
        request = self.context.get('request')
        if request and not request.user.is_staff:
            # Non-staff users ko internal_notes mat dikho
            result.pop('internal_notes', None)
        
        print(f"[to_representation] Final output: {result}")
        return result


# Serializer Flow Summary:
#
# CREATE (POST):
# request.data → serializer(data=request.data) → is_valid()
#   → to_internal_value() → validate_<field>() → validate()
#   → serializer.save() → create(validated_data)
#   → to_representation(new_instance) → Response
#
# READ (GET):
# queryset/instance → serializer(instance) → serializer.data
#   → to_representation(instance) → dict → JSON Response
```

### Content Negotiation — How Format Decide Hota Hai?

```python
# DRF content negotiation:
# Client: "Accept: application/json" ya "Accept: text/html" bhejta hai
# DRF: Available renderers mein se best match dhundta hai

# settings.py
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',       # JSON response
        'rest_framework.renderers.BrowsableAPIRenderer', # HTML browser view
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',           # JSON body parse karo
        'rest_framework.parsers.MultiPartParser',      # File uploads
        'rest_framework.parsers.FormParser',           # HTML form data
    ],
}

# Per-view override karo:
class ProductViewSet(viewsets.ModelViewSet):
    renderer_classes = [JSONRenderer]  # Sirf JSON, no browser view
    parser_classes = [JSONParser]      # Sirf JSON input accept karo

# ?format=json URL parameter se bhi control kar sakte hain:
# /api/products/?format=json  → JSONRenderer use hoga
# /api/products/?format=api   → BrowsableAPIRenderer use hoga
```

---

## Interview Questions & Answers

### Q1: Django request lifecycle mein middleware ka order matter karta hai kya?

**Answer:**
Haan, bahut zyada. `process_request` top-to-bottom order mein chalta hai, `process_response` bottom-to-top. Matlab pehle wala middleware sabse outer layer hai.

Practical impact:
- `SecurityMiddleware` pehle hona chahiye — HTTPS redirect, security headers set karta hai
- `SessionMiddleware` `AuthenticationMiddleware` se pehle hona chahiye — kyunki Auth middleware session se user dhundta hai
- Agar aap custom middleware mein `request.user` access karna chahte ho, toh aapka middleware `AuthenticationMiddleware` ke baad hona chahiye

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',      # 1st — security
    'django.contrib.sessions.middleware.SessionMiddleware', # 2nd — session setup
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware', # 5th — user set
    # Aapka middleware yahan — request.user available hai
    'myapp.middleware.MyCustomMiddleware',
]
```

### Q2: Signals vs Database Transactions — Kya Issue Ho Sakta Hai?

**Answer:**
Bahut important gotcha! `post_save` signal transaction ke andar fire hota hai. Agar Celery task signal mein queue karo aur transaction rollback ho jaaye — task run ho chuki hogi par DB changes revert ho gaye.

```python
# PROBLEM:
@receiver(post_save, sender=Order)
def notify_on_order(sender, instance, created, **kwargs):
    if created:
        # ❌ Transaction abhi commit nahi hua!
        # Celery task run karte time Order DB mein nahi milegi
        send_order_email.delay(instance.id)


# SOLUTION — transaction.on_commit use karo:
from django.db import transaction

@receiver(post_save, sender=Order)
def notify_on_order(sender, instance, created, **kwargs):
    if created:
        # ✅ Transaction commit hone KE BAAD task queue hoga
        transaction.on_commit(
            lambda: send_order_email.delay(instance.id)
        )
```

### Q3: Async view mein blocking ORM call directly karein toh kya hoga?

**Answer:**
`django.core.exceptions.SynchronousOnlyOperation` exception raise hogi. Django ka ORM internally thread-local connections use karta hai aur async context mein direct call karne ki permission nahi hai.

```python
# ❌ GALAT — Exception aayegi:
async def bad_view(request):
    users = list(User.objects.all())  # SynchronousOnlyOperation!

# ✅ SAHI — Wrapper use karo:
async def good_view(request):
    # Option 1: sync_to_async
    users = await sync_to_async(list)(User.objects.all())
    
    # Option 2: Django 4.1+ native async ORM
    count = await User.objects.acount()
```

**Why ye exception aati hai?**
Django ka ORM database connections ko thread-safe rakhta hai. Async context mein (event loop thread mein), ORM ko directly call karne se multiple coroutines ek hi DB connection corrupt kar sakti hain.

### Q4: DRF mein authentication aur authorization ka fark explain karo?

**Answer:**
- **Authentication** = "Tum kaun ho?" — Identity verify karo (JWT token valid hai? Session valid hai?)
- **Authorization** = "Tum ye kar sakte ho?" — Permission check karo (Is user ko is resource pe access hai?)

DRF flow:
1. `initial()` → `perform_authentication()` → `request.user` set hota hai (Authentication)
2. `initial()` → `check_permissions()` → Permission classes check karti hain (Authorization)

```python
# Authentication classes:
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    # Har request pe pehle JWT try hota hai, fail toh Session try
}

# Permission classes:
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
```

### Q5: Custom signal mein `**kwargs` kyu zaroori hai?

**Answer:**
Signal receivers mein `**kwargs` hamesha rakho. Django signals future mein naye arguments add kar sakta hai. Agar `**kwargs` nahi hai aur Django naya argument bheje, toh `TypeError` aayegi.

```python
# ❌ Risky:
@receiver(post_save, sender=User)
def my_receiver(sender, instance, created):  # Agar Django naya kwarg add kare → TypeError
    pass

# ✅ Safe:
@receiver(post_save, sender=User)
def my_receiver(sender, instance, created, **kwargs):  # Extra args safely absorb ho jaate hain
    pass
```

### Q6: DRF `get_queryset()` vs `queryset = ...` class attribute mein fark?

**Answer:**
```python
# Class attribute — SAME queryset sabke liye, server startup pe evaluate hota hai
class ProductViewSet(ModelViewSet):
    queryset = Product.objects.all()  # Request-independent, cached

# Method — har request pe fresh queryset, request context available hai
class ProductViewSet(ModelViewSet):
    def get_queryset(self):
        # Request ke hisaab se filter kar sakte ho
        return Product.objects.filter(
            owner=self.request.user  # ← request.user available hai
        )
```

**Gotcha:** Class attribute wale queryset mein `request.user` access nahi kar sakte. Dynamic filtering ke liye `get_queryset()` override karo.

### Q7: Signal ka `dispatch_uid` kab use karo?

**Answer:**
Jab signal accidentally multiple baar register ho jaaye — especially `ready()` mein hot reload ke waqt. `dispatch_uid` ensure karta hai ki same receiver ek hi baar register ho.

```python
# Problem: Development server reload karne pe signal double-register ho sakta hai
@receiver(post_save, sender=User, dispatch_uid="users.create_profile")
def create_user_profile(sender, instance, created, **kwargs):
    # dispatch_uid unique string hai — same UID wala receiver dobara register nahi hoga
    if created:
        Profile.objects.create(user=instance)
```

### Q8: `async_to_sync` kab use karte hain?

**Answer:**
Jab sync code ke andar async function call karna ho — jaise management commands, Celery tasks, ya tests.

```python
from asgiref.sync import async_to_sync

# Management command mein async function call karo
class Command(BaseCommand):
    def handle(self, *args, **options):
        # Ye synchronous context hai
        result = async_to_sync(self.async_work)()
        self.stdout.write(f"Done: {result}")
    
    async def async_work(self):
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.example.com/data")
            return response.json()

# Celery task mein:
@celery_app.task
def sync_celery_task(user_id):
    # Celery workers sync context mein chalte hain
    async def fetch_data():
        count = await User.objects.filter(id=user_id).acount()
        return count
    
    return async_to_sync(fetch_data)()
```
