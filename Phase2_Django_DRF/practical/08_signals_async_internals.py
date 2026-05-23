"""
Django Internals, Signals & Async — Practical Demonstrations
=============================================================

Ye file STANDALONE demonstration hai — seedha copy karo apne Django project mein.
Har section clearly marked hai. Hinglish comments explain karte hain WHY kuch kaam karta hai.

HOW TO USE:
- Har section ek alag file/concept represent karta hai
- Copy-paste karo apne project structure mein
- Section headers mein file path diya hai

Requirements:
    pip install django djangorestframework httpx celery

Author: Study Notes — Django Advanced Internals
"""

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: MIDDLEWARE — Request/Response Lifecycle Trace Karo
# File: myproject/middleware.py
# ═══════════════════════════════════════════════════════════════════════════════

import time
import uuid
import logging
import asyncio

logger = logging.getLogger(__name__)


class RequestLifecycleMiddleware:
    """
    Har HTTP request ka poora lifecycle trace karta hai.

    Django Middleware kaise kaam karta hai:
    - __init__: Server startup pe SIRF EK BAAR — configuration yahan karo
    - __call__: HAR REQUEST PE — pre/post view logic yahan

    Order matters! settings.py MIDDLEWARE list mein:
        process_request  → TOP se BOTTOM (request aate time)
        process_response → BOTTOM se TOP (response jaate time)
    """

    def __init__(self, get_response):
        """
        get_response = next middleware ya actual view — ek callable.
        Ye ek baar call hota hai jab Django application start hota hai.
        """
        self.get_response = get_response
        print("[MIDDLEWARE INIT] RequestLifecycleMiddleware initialized — app startup pe ek baar")

    def __call__(self, request):
        # ─── BEFORE VIEW (process_request equivalent) ───────────────────────
        request_id = str(uuid.uuid4())[:8]
        request._request_id = request_id
        start_time = time.monotonic()

        print(f"\n{'='*60}")
        print(f"[→ REQUEST START] ID={request_id}")
        print(f"  Method : {request.method}")
        print(f"  Path   : {request.path}")
        print(f"  IP     : {self._get_client_ip(request)}")
        print(f"  User   : {getattr(request, 'user', 'not-authenticated-yet')}")
        # Note: request.user yahan None/AnonymousUser ho sakta hai
        # AuthenticationMiddleware baad mein aata hai!

        # ─── ACTUAL VIEW CALL ────────────────────────────────────────────────
        # Ye line ke andar:
        # 1. Baki middleware ka __call__ chalega
        # 2. URL resolver match karega
        # 3. Actual view execute hoga
        # 4. Response wapas aayega
        response = self.get_response(request)

        # ─── AFTER VIEW (process_response equivalent) ────────────────────────
        duration_ms = (time.monotonic() - start_time) * 1000

        print(f"[← RESPONSE END] ID={request_id}")
        print(f"  Status : {response.status_code}")
        print(f"  Time   : {duration_ms:.2f}ms")
        print(f"{'='*60}\n")

        # Custom headers add karo — client ko bhi dikhe
        response['X-Request-ID'] = request_id
        response['X-Process-Time'] = f"{duration_ms:.2f}ms"

        return response

    def process_exception(self, request, exception):
        """
        View ya neeche ke middleware mein unhandled exception aaye toh Django ye call karta hai.

        Return None   → Django ki default exception handling chalti hai (500 page ya DEBUG traceback)
        Return HttpResponse → Custom error response dene ke liye
        """
        print(f"[EXCEPTION] {request.method} {request.path}")
        print(f"  Type   : {type(exception).__name__}")
        print(f"  Detail : {exception}")

        # Yahan Sentry ya error tracking service ko notify kar sakte ho
        # sentry_sdk.capture_exception(exception)

        return None  # Django ko handle karne do

    @staticmethod
    def _get_client_ip(request):
        """
        Real client IP dhundho — load balancer/reverse proxy ke peeche bhi kaam kare.
        X-Forwarded-For header mein comma-separated list hoti hai:
            client_ip, proxy1_ip, proxy2_ip
        """
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


# ─── settings.py mein register karo: ────────────────────────────────────────
#
# MIDDLEWARE = [
#     'django.middleware.security.SecurityMiddleware',
#     'myproject.middleware.RequestLifecycleMiddleware',  # ← yahan add karo
#     'django.contrib.sessions.middleware.SessionMiddleware',
#     'django.middleware.common.CommonMiddleware',
#     'django.middleware.csrf.CsrfViewMiddleware',
#     'django.contrib.auth.middleware.AuthenticationMiddleware',
#     'django.contrib.messages.middleware.MessageMiddleware',
#     'django.middleware.clickjacking.XFrameOptionsMiddleware',
# ]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: SIGNALS — 5 Working Examples
# Files:
#   users/apps.py   — AppConfig with ready()
#   users/signals.py — All signal receivers
# ═══════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# FILE: users/apps.py
# ─────────────────────────────────────────────────────────────────────────────
# from django.apps import AppConfig
#
# class UsersConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'users'
#
#     def ready(self):
#         """
#         Django ka poora app loaded hone ke baad SIRF EK BAAR call hota hai.
#
#         Yahan signals import karo — is waqt tak:
#         - Saare models loaded hain
#         - Saare apps initialize ho chuke hain
#         - Circular import ka risk nahi hai
#
#         Yahan MAT karo:
#         - Database queries (migrations ke waqt DB ready nahi hota)
#         - Heavy computation (startup slow ho jaayegi)
#         """
#         import users.signals  # noqa — side effect: signal registration

# ─────────────────────────────────────────────────────────────────────────────
# FILE: users/signals.py
# ─────────────────────────────────────────────────────────────────────────────

# Actual imports jo real file mein honge:
# from django.db.models.signals import post_save, pre_delete, m2m_changed
# from django.dispatch import receiver, Signal
# from django.contrib.auth import get_user_model
# from django.utils import timezone
# User = get_user_model()


# ══ EXAMPLE 1: post_save — Profile Auto-Create ════════════════════════════════

def demo_post_save_profile_create():
    """
    Jab naya User create ho, automatically Profile banao.

    WHY post_save aur pre_save nahi?
    - pre_save pe user ka ID nahi hota abhi (INSERT nahi hua)
    - post_save pe ID available hota hai → Profile mein ForeignKey set kar sako
    """
    print("\n--- DEMO: post_save signal — Profile auto-create ---")

    # Actual signal code:
    # @receiver(post_save, sender=User)
    # def create_user_profile(sender, instance, created, **kwargs):
    #     """
    #     sender   = User class (kaunsi model se signal aaya)
    #     instance = actual User object jo save hua
    #     created  = True agar naya record INSERT hua, False agar UPDATE
    #     **kwargs = raw, update_fields, signal — future-proof ke liye zaroori!
    #     """
    #     if created:
    #         # Local import — circular import avoid karo
    #         from users.models import Profile
    #         profile = Profile.objects.create(user=instance)
    #         print(f"[SIGNAL] Profile auto-created for: {instance.email}")
    #         print(f"[SIGNAL] Profile ID: {profile.id}")

    # Simulate karo:
    class FakeUser:
        id = 42
        email = "john@example.com"
        username = "john"

    class FakeProfile:
        id = 99
        user = None

    instance = FakeUser()
    created = True

    # Signal logic simulate:
    if created:
        # Profile.objects.create(user=instance) hoga real mein
        profile = FakeProfile()
        profile.user = instance
        print(f"[SIGNAL FIRED] post_save — sender=User, created={created}")
        print(f"[SIGNAL] Profile auto-created for user: {instance.email}")
        print(f"[SIGNAL] WHY: User aur Profile tightly coupled nahi hain — signal loosely couple karta hai")


demo_post_save_profile_create()


# ══ EXAMPLE 2: post_save + Celery — Welcome Email ════════════════════════════

def demo_post_save_welcome_email():
    """
    Naye user ko welcome email bhejo — Celery se async mein.

    WHY signal mein directly email nahi bhejte?
    - Email SMTP call blocking hoti hai (200-500ms)
    - Request slow ho jaayegi
    - SMTP fail hone pe user creation bhi fail ho sakti thi

    CORRECT PATTERN: Signal → Celery task queue → Background worker → Email send
    """
    print("\n--- DEMO: post_save + Celery — Welcome email async ---")

    # Actual signal code:
    # @receiver(post_save, sender=User, dispatch_uid="users.send_welcome_email")
    # def send_welcome_email(sender, instance, created, **kwargs):
    #     """
    #     dispatch_uid="users.send_welcome_email"
    #     WHY dispatch_uid? Development hot-reload mein signal double-register ho sakta hai.
    #     dispatch_uid ensure karta hai: same UID wala receiver sirf ONCE register ho.
    #     """
    #     if created:
    #         from django.db import transaction
    #         # transaction.on_commit — CRITICAL!
    #         # Bina iske: Celery task chale, lekin DB transaction rollback ho jaaye
    #         # → Celery task try kare User dhundhna → DoesNotExist exception!
    #         transaction.on_commit(
    #             lambda: send_welcome_email_task.delay(
    #                 user_id=instance.id,
    #                 email=instance.email,
    #                 name=instance.get_full_name() or instance.username,
    #             )
    #         )
    #         print(f"[SIGNAL] Welcome email queued for: {instance.email}")

    print("[SIGNAL] post_save fired — Celery task queue ho raha hai")
    print("[SIGNAL] WHY on_commit: Transaction commit ke BAAD task queue hoga")
    print("[SIGNAL] WHY Celery: Email send karna blocking I/O hai — background mein karo")
    print("[SIGNAL] dispatch_uid use kiya — double-registration se bachao")


demo_post_save_welcome_email()


# ══ EXAMPLE 3: pre_delete — Audit Log ════════════════════════════════════════

def demo_pre_delete_audit_log():
    """
    User delete hone se PEHLE audit log banao.

    WHY pre_delete aur post_delete nahi?
    - pre_delete pe: object still DB mein hai, uska data available hai
    - post_delete pe: object delete ho chuka — related data bhi cascade se ja sakta hai
    - Audit log ke liye complete data chahiye → pre_delete better hai
    """
    print("\n--- DEMO: pre_delete signal — Audit log ---")

    # Actual signal code:
    # @receiver(pre_delete, sender=User)
    # def log_user_deletion(sender, instance, **kwargs):
    #     """
    #     Yahan extra_data mein saari info save karo — delete ke baad pata nahi chalega
    #     """
    #     from audit.models import AuditLog
    #     AuditLog.objects.create(
    #         action="USER_DELETED",
    #         object_id=instance.id,
    #         object_repr=f"User<{instance.email}>",
    #         extra_data={
    #             "username":    instance.username,
    #             "email":       instance.email,
    #             "is_staff":    instance.is_staff,
    #             "date_joined": instance.date_joined.isoformat(),
    #             "last_login":  instance.last_login.isoformat() if instance.last_login else None,
    #         },
    #         timestamp=timezone.now(),
    #     )
    #     print(f"[SIGNAL] Audit log created — User {instance.email} being deleted")

    class FakeUser:
        id = 10
        email = "to_delete@example.com"
        username = "to_delete"
        is_staff = False

    instance = FakeUser()
    print(f"[SIGNAL FIRED] pre_delete — User: {instance.email}")
    print(f"[SIGNAL] Audit log entry created: {{action: 'USER_DELETED', user_id: {instance.id}}}")
    print("[SIGNAL] WHY pre_delete: Object abhi DB mein hai — poora data capture kar sako")


demo_pre_delete_audit_log()


# ══ EXAMPLE 4: Custom Signal — Payment Completed ══════════════════════════════

def demo_custom_signal():
    """
    Custom signal banao aur multiple receivers connect karo.

    WHY custom signal?
    - Django ke built-in signals sirf model events ke liye hain
    - Business events ke liye (payment, shipment, etc.) custom signals better hain
    - Multiple teams/apps ek hi event pe react kar sakti hain without coupling
    """
    print("\n--- DEMO: Custom signal — payment_completed ---")

    # Actual code:
    # payments/signals.py:
    # from django.dispatch import Signal
    #
    # payment_completed = Signal()
    # payment_failed    = Signal()
    #
    # def process_payment(user, amount, order_id):
    #     try:
    #         # ... payment gateway call ...
    #         payment_completed.send(
    #             sender=None,          # Ya sender=PaymentService
    #             user=user,
    #             amount=amount,
    #             order_id=order_id,
    #             currency="INR",
    #         )
    #     except PaymentGatewayError as e:
    #         payment_failed.send(
    #             sender=None,
    #             user=user,
    #             amount=amount,
    #             order_id=order_id,
    #             error_message=str(e),
    #         )
    #
    # # Receiver 1 — orders app mein (order status update)
    # @receiver(payment_completed)
    # def update_order_status(sender, user, amount, order_id, **kwargs):
    #     Order.objects.filter(id=order_id).update(status='paid')
    #     print(f"[SIGNAL] Order {order_id} marked as paid")
    #
    # # Receiver 2 — notifications app mein (receipt email)
    # @receiver(payment_completed)
    # def send_payment_receipt(sender, user, amount, order_id, **kwargs):
    #     from django.db import transaction
    #     transaction.on_commit(
    #         lambda: send_receipt_task.delay(user.id, str(amount), order_id)
    #     )
    #     print(f"[SIGNAL] Receipt email queued for order {order_id}")
    #
    # # Receiver 3 — analytics app mein (revenue tracking)
    # @receiver(payment_completed)
    # def track_revenue(sender, user, amount, order_id, currency, **kwargs):
    #     RevenueEvent.objects.create(user=user, amount=amount, currency=currency)
    #     print(f"[SIGNAL] Revenue event tracked: {currency} {amount}")

    # Simulate multiple receivers:
    class FakeSignal:
        def __init__(self, name):
            self.name = name
            self.receivers = []

        def connect(self, fn):
            self.receivers.append(fn)

        def send(self, sender=None, **kwargs):
            print(f"[SIGNAL '{self.name}'] Fired! Notifying {len(self.receivers)} receivers...")
            results = []
            for receiver_fn in self.receivers:
                result = receiver_fn(sender=sender, **kwargs)
                results.append(result)
            return results

    payment_completed = FakeSignal("payment_completed")

    def update_order_status(sender, user, amount, order_id, **kwargs):
        print(f"  [Receiver 1] Order {order_id} → status='paid'")

    def send_payment_receipt(sender, user, amount, order_id, **kwargs):
        print(f"  [Receiver 2] Receipt email queued for ₹{amount}")

    def track_revenue(sender, user, amount, order_id, **kwargs):
        print(f"  [Receiver 3] Revenue event tracked: ₹{amount}")

    payment_completed.connect(update_order_status)
    payment_completed.connect(send_payment_receipt)
    payment_completed.connect(track_revenue)

    print("[SENDING] payment_completed.send() call ho raha hai...")
    payment_completed.send(
        sender=None,
        user=type('User', (), {'id': 1, 'email': 'buyer@example.com'})(),
        amount=1499.00,
        order_id="ORD-2024-001",
    )
    print("[RESULT] Teeno receivers notify ho gaye — payment_completed signal!")
    print("[WHY CUSTOM SIGNAL] Orders, Notifications, Analytics sab alag apps hain")
    print("                    Par ek event pe react karte hain — loose coupling!")


demo_custom_signal()


# ══ EXAMPLE 5: m2m_changed Signal ════════════════════════════════════════════

def demo_m2m_changed():
    """
    ManyToMany field change hone pe action lo.

    WHY m2m_changed?
    - post_save SIRF model ke direct fields ke liye fire hota hai
    - M2M changes alag table mein hote hain — alag signal chahiye
    - action parameter se exact operation pata chalti hai
    """
    print("\n--- DEMO: m2m_changed — User groups track karo ---")

    # Actual signal code:
    # @receiver(m2m_changed, sender=User.groups.through)
    # def on_user_groups_changed(sender, instance, action, pk_set, model, **kwargs):
    #     """
    #     sender   = User.groups.through (intermediary table)
    #     instance = User object (jiska groups change hua)
    #     action   = "pre_add" | "post_add" | "pre_remove" | "post_remove" | "pre_clear" | "post_clear"
    #     pk_set   = set of Group PKs jo add/remove hue
    #     model    = Group model class
    #     """
    #     if action == "post_add":
    #         from django.contrib.auth.models import Group
    #         group_names = list(Group.objects.filter(pk__in=pk_set).values_list('name', flat=True))
    #         print(f"[M2M SIGNAL] User '{instance.email}' added to: {group_names}")
    #
    #         # Agar 'admin' group mein add hua → extra notification bhejo
    #         if 'admin' in group_names:
    #             notify_security_team.delay(user_id=instance.id, action='admin_granted')
    #
    #     elif action == "post_remove":
    #         print(f"[M2M SIGNAL] User '{instance.email}' removed from groups: {pk_set}")
    #
    #     elif action == "post_clear":
    #         print(f"[M2M SIGNAL] User '{instance.email}' removed from ALL groups")

    # Simulate:
    actions = [
        ("post_add",    {1, 2},  "Groups added"),
        ("post_remove", {2},     "Group removed"),
        ("post_clear",  set(),   "All groups cleared"),
    ]
    for action, pk_set, description in actions:
        print(f"[M2M SIGNAL FIRED] action='{action}', pk_set={pk_set} → {description}")

    print("[WHY m2m_changed] post_save se nahi milta M2M change notification")
    print("                  M2M updates alag through-table mein hote hain")


demo_m2m_changed()


# ══ EXAMPLE 5b: Test Mein Signal Disconnect ═══════════════════════════════════

def demo_signal_disconnect_in_tests():
    """
    Tests mein signals disconnect karna kyun zaroori hai.

    PROBLEM without disconnect:
    - User create karo test mein → post_save fires → Profile create hone ki koshish
    - Profile model ka mock nahi kiya → IntegrityError ya unexpected DB hit
    - Celery broker nahi hai test mein → task queue fail

    SOLUTION: disconnect karo → test karo → reconnect karo
    """
    print("\n--- DEMO: Test mein signal disconnect ---")

    print("# Method 1 — Manually disconnect/reconnect:")
    print("""
    from django.db.models.signals import post_save
    from users.signals import create_user_profile
    from django.contrib.auth import get_user_model

    User = get_user_model()

    def test_user_creation():
        post_save.disconnect(create_user_profile, sender=User)
        try:
            user = User.objects.create_user(username='test', email='t@t.com')
            assert user.email == 't@t.com'
        finally:
            # HAMESHA finally mein reconnect — test fail hone pe bhi
            post_save.connect(create_user_profile, sender=User)
    """)

    print("# Method 2 — mock.patch (cleaner approach):")
    print("""
    from unittest.mock import patch

    def test_user_with_mock():
        with patch('users.signals.create_user_profile') as mock_signal:
            user = User.objects.create_user(username='test2', email='t2@t.com')
            # Signal fire hua par mocked function chala — no side effects
            mock_signal.assert_called_once()
    """)

    print("# Method 3 — factory_boy (best practice for large projects):")
    print("""
    import factory

    class UserFactory(factory.django.DjangoModelFactory):
        class Meta:
            model = User
            # Signals automatically handle ho jaate hain
            # Ya explicitly:
            # exclude = ['_disable_signals']

        username = factory.Sequence(lambda n: f'user{n}')
        email = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    """)


demo_signal_disconnect_in_tests()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: ASYNC DJANGO VIEWS — Complete Patterns
# File: myapp/views_async.py
# ═══════════════════════════════════════════════════════════════════════════════

def demo_async_views():
    """
    Async Django views ke sare patterns demonstrate karta hai.

    Prerequisites:
    - Django 3.1+ for async views
    - Django 4.1+ for native async ORM (aget, afilter, etc.)
    - ASGI server: uvicorn ya daphne (gunicorn=WSGI only)
    - pip install httpx  (for external API calls)
    """
    print("\n" + "═"*60)
    print("SECTION 3: Async Django Views")
    print("═"*60)


# ─── Code Template: Async Views (copy karo views.py mein) ────────────────────

ASYNC_VIEWS_CODE = '''
# myapp/views_async.py
# pip install httpx asyncio (asyncio standard library hai)

import asyncio
import httpx
from django.http import JsonResponse
from asgiref.sync import sync_to_async, async_to_sync
from django.contrib.auth import get_user_model

User = get_user_model()


# ══ PATTERN 1: Basic Async View ═══════════════════════════════════════════════

async def async_hello_view(request):
    """
    Simplest async view.
    Django ASGI mein ye event loop pe run hota hai — thread block nahi hogi.
    """
    return JsonResponse({"message": "Hello from async!", "thread": "non-blocking"})


# ══ PATTERN 2: Django 4.1+ Native Async ORM ══════════════════════════════════

async def async_user_stats(request):
    """
    Django 4.1+ ke async ORM methods:
    - acount()  — queryset ka count
    - aget()    — single object (raises DoesNotExist/MultipleObjects)
    - aexists() — queryset mein kuch hai kya?
    - acreate() — naya object banao
    - aupdate() — bulk update
    - adelete() — bulk delete
    - aiterator() — large queryset iterate karo (memory-efficient)
    """
    # count — await karo directly
    active_count = await User.objects.filter(is_active=True).acount()

    # get — single object fetch
    try:
        admin_user = await User.objects.aget(is_superuser=True)
        admin_name = admin_user.username
    except User.DoesNotExist:
        admin_name = "No admin found"

    # exists — boolean check
    has_staff = await User.objects.filter(is_staff=True).aexists()

    return JsonResponse({
        "active_users": active_count,
        "admin": admin_name,
        "has_staff": has_staff,
    })


# ══ PATTERN 3: sync_to_async — Purani Code Wrap Karo ═════════════════════════

async def async_product_detail(request, product_id):
    """
    sync_to_async kab use karo:
    - Third-party library jo async support nahi karti
    - Complex queryset jo Django 4.1 mein bhi async support nahi karta
      (e.g., iterator(), values(), ValuesQuerySet ka direct access)
    - Custom manager methods jo sync hain

    thread_sensitive=True  (default) — ORM ke liye ZAROOR rakho
    thread_sensitive=False — Pure computation ke liye use karo
    """
    from myapp.models import Product

    # Method 1 — Wrap karo explicit function ko
    @sync_to_async
    def get_product_with_relations(pid):
        """
        Yahan freely sync ORM likh sakte ho.
        Ye ek separate thread mein chalega — event loop block nahi hoga.
        """
        from myapp.models import Product
        try:
            return Product.objects.select_related(
                'category', 'brand'
            ).prefetch_related(
                'tags', 'reviews'
            ).get(id=pid)
        except Product.DoesNotExist:
            return None

    product = await get_product_with_relations(product_id)
    if not product:
        return JsonResponse({"error": "Product not found"}, status=404)

    return JsonResponse({
        "id": product.id,
        "name": product.name,
        "price": str(product.price),
        "category": product.category.name,
    })


# ══ PATTERN 4: asyncio.gather — Parallel DB Queries ═════════════════════════

async def dashboard_stats(request):
    """
    Multiple independent queries PARALLEL mein chalao.

    Sequential time:  query1(100ms) + query2(100ms) + query3(100ms) = 300ms
    Parallel time:    max(100ms, 100ms, 100ms) = ~100ms  ← 3x faster!

    asyncio.gather ye sab concurrently start karta hai.
    """
    from myapp.models import Product, Order

    # Sab ek saath start ho jaate hain — gather sab complete hone ka wait karta hai
    user_count, product_count, pending_orders, total_revenue = await asyncio.gather(
        User.objects.filter(is_active=True).acount(),
        Product.objects.filter(is_available=True).acount(),
        Order.objects.filter(status='pending').acount(),
        # Complex aggregation — sync_to_async use karo
        sync_to_async(lambda: Order.objects.filter(
            status='completed'
        ).aggregate(
            total=models.Sum('amount')
        )['total'] or 0)(),
    )

    return JsonResponse({
        "active_users":    user_count,
        "products":        product_count,
        "pending_orders":  pending_orders,
        "total_revenue":   float(total_revenue),
    })


# ══ PATTERN 5: External API — httpx.AsyncClient ═══════════════════════════════

async def fetch_weather(request, city: str):
    """
    External HTTP calls ke liye httpx use karo.

    WHY httpx aur requests nahi?
    - requests library SYNCHRONOUS hai — async context mein use karo toh event loop block!
    - httpx.AsyncClient proper async HTTP client hai

    WHY context manager (async with)?
    - Connection pool properly close hota hai
    - Connections leak nahi hoti
    """
    api_url = "https://api.openweathermap.org/data/2.5/weather"
    api_key = "your_openweathermap_api_key"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            response = await client.get(
                api_url,
                params={"q": city, "appid": api_key, "units": "metric"},
            )
            response.raise_for_status()  # 4xx/5xx pe exception
            data = response.json()

        return JsonResponse({
            "city":        data["name"],
            "temperature": data["main"]["temp"],
            "feels_like":  data["main"]["feels_like"],
            "description": data["weather"][0]["description"],
            "humidity":    data["main"]["humidity"],
        })

    except httpx.TimeoutException:
        return JsonResponse({"error": "Weather API timed out"}, status=504)
    except httpx.HTTPStatusError as e:
        return JsonResponse({"error": f"Weather API error: {e.response.status_code}"}, status=502)
    except Exception as e:
        return JsonResponse({"error": "Unexpected error"}, status=500)


# ══ PATTERN 6: Multiple External APIs — True Parallelism ═════════════════════

async def product_enriched_view(request, product_id: int):
    """
    Ek product ke saath reviews aur inventory bhi fetch karo — parallel mein!
    """
    from myapp.models import Product

    product = await Product.objects.aget(id=product_id)

    async with httpx.AsyncClient(timeout=5.0) as client:
        # Dono API calls simultaneously fire hoti hain
        results = await asyncio.gather(
            client.get(f"https://reviews-api.internal/products/{product_id}/reviews"),
            client.get(f"https://inventory-api.internal/stock/{product_id}"),
            return_exceptions=True,  # Ek fail hone pe doosra cancel nahi hoga
        )

    reviews_resp, inventory_resp = results

    reviews   = reviews_resp.json()   if not isinstance(reviews_resp, Exception)   else []
    inventory = inventory_resp.json() if not isinstance(inventory_resp, Exception) else {}

    return JsonResponse({
        "product":   {"id": product.id, "name": product.name, "price": str(product.price)},
        "reviews":   reviews,
        "inventory": inventory,
    })


# ══ PATTERN 7: WRONG vs RIGHT — SynchronousOnlyOperation ═════════════════════

# ❌ GALAT — Django < 4.1 mein crash ho jaayega:
# async def bad_view(request):
#     users = list(User.objects.all())  # django.core.exceptions.SynchronousOnlyOperation!
#     products = Product.objects.filter(is_active=True)  # SynchronousOnlyOperation!
#     return JsonResponse({"count": users.count()})  # Crash!

# ✅ SAHI — Correct patterns:
async def correct_async_view(request):
    # Option A — Django 4.1+ native
    count_a = await User.objects.filter(is_active=True).acount()

    # Option B — sync_to_async wrapper
    count_b = await sync_to_async(
        lambda: User.objects.filter(is_active=True).count()
    )()

    # Option C — Function wrap karo
    @sync_to_async
    def get_active_users():
        return list(User.objects.filter(is_active=True).values('id', 'email'))

    users = await get_active_users()

    return JsonResponse({"count": count_a, "users": users})
'''

demo_async_views()
print("[ASYNC VIEWS CODE TEMPLATE]")
print("Upar diya hua code copy karo apne views.py mein.")
print("\nKey points:")
print("  1. Django 4.1+ → native async ORM methods use karo (aget, acount, etc.)")
print("  2. Django < 4.1 → sync_to_async wrapper zaroori hai ORM ke liye")
print("  3. External HTTP calls → httpx.AsyncClient use karo (requests nahi!)")
print("  4. Multiple queries → asyncio.gather se parallel chalao")
print("  5. SynchronousOnlyOperation = async context mein direct ORM call")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: DRF INTERNALS — Dispatch Flow, Auth, Serializer Pipeline
# File: myapp/views_drf_internals.py
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "═"*60)
print("SECTION 4: DRF Internals — dispatch() flow trace karo")
print("═"*60)

DRF_INTERNALS_CODE = '''
# myapp/views_drf_internals.py
# DRF ke internal flow ko trace karna — debugging aur advanced customization ke liye

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets, serializers, status
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission
from decimal import Decimal


# ══ PART A: DRF Dispatch Flow Trace ══════════════════════════════════════════

class TracedAPIView(APIView):
    """
    DRF ke har lifecycle method ko override karke print karo.
    Production mein mat use karo — sirf learning ke liye.

    DRF dispatch() ka order:
    1. initialize_request()  — Django request → DRF Request wrap
    2. initial()             — auth + permissions + throttle
       2a. perform_authentication()
       2b. check_permissions()
       2c. check_throttles()
    3. get()/post()/etc.     — Actual view method
    """

    def initialize_request(self, request, *args, **kwargs):
        """
        Pehla step: Django ka raw HttpRequest ko DRF Request mein wrap karo.

        DRF Request jo add karta hai Django Request ke upar:
        - request.data          (request.POST/body parsed correctly)
        - request.query_params  (request.GET ka readable alias)
        - request.auth          (authentication object — token, etc.)
        - request.authenticators (list of auth classes from settings)
        - request.accepted_renderer (content negotiation result)
        - request._request      (original Django HttpRequest)
        """
        print("\n[DRF] Step 1: initialize_request()")
        print("      Django HttpRequest → DRF Request wrap ho raha hai")
        print(f"      Original request type: {type(request).__name__}")

        drf_request = super().initialize_request(request, *args, **kwargs)

        print(f"      DRF Request type: {type(drf_request).__name__}")
        print(f"      Authenticators: {[type(a).__name__ for a in drf_request.authenticators]}")
        print(f"      Parsers: {[type(p).__name__ for p in drf_request.parsers]}")

        return drf_request

    def initial(self, request, *args, **kwargs):
        """
        Doosra step: Authentication, permissions, throttling.

        Ye method teen kaam karta hai sequence mein:
        1. perform_authentication() → request.user set karo
        2. check_permissions()      → access allow hai?
        3. check_throttles()        → rate limit check
        """
        print("\n[DRF] Step 2: initial()")
        print("      Authentication + Permissions + Throttling check")

        super().initial(request, *args, **kwargs)

        print(f"      Authenticated user: {request.user}")
        print(f"      Auth object: {request.auth}")

    def get(self, request, *args, **kwargs):
        """Teesra step: Actual view logic"""
        print("\n[DRF] Step 3: get() — view method execute ho raha hai")
        print("      Business logic yahan aata hai")
        return Response({
            "message": "DRF dispatch flow traced!",
            "user": str(request.user),
        })


# ══ PART B: Custom Authentication Backend ════════════════════════════════════

class APIKeyAuthentication(BaseAuthentication):
    """
    Custom API Key authentication.

    DRF Authentication Protocol:
    - authenticate() method implement karo
    - Return (user, auth) tuple agar success
    - Return None agar ye authenticator applicable nahi (doosra try hoga)
    - Raise AuthenticationFailed agar credentials wrong hain

    Multiple authenticators settings mein daal sakte ho:
    DEFAULT_AUTHENTICATION_CLASSES = [JWTAuth, APIKeyAuthentication, SessionAuth]
    Har request pe list iterate hoti hai — pehla jo None nahi return kare, woh win karta hai.
    """

    HEADER_NAME = 'HTTP_X_API_KEY'  # Header: X-Api-Key

    def authenticate(self, request):
        api_key = request.META.get(self.HEADER_NAME)

        if not api_key:
            # Ye header nahi hai → mera kaam nahi → doosra authenticator try hoga
            print("[APIKeyAuth] X-Api-Key header nahi mila → None return")
            return None

        print(f"[APIKeyAuth] API Key mila: {api_key[:8]}...")

        try:
            # APIKey model assume kar rahe hain — apna model use karo
            from myapp.models import APIKey
            key_obj = APIKey.objects.select_related('user').get(
                key=api_key,
                is_active=True,
            )
            print(f"[APIKeyAuth] Valid key! User: {key_obj.user.email}")
            return (key_obj.user, key_obj)  # (user, auth_object) tuple

        except APIKey.DoesNotExist:
            # Key wrong ya inactive → exception raise karo
            raise AuthenticationFailed("Invalid or inactive API Key")

    def authenticate_header(self, request):
        """
        Ye string 401 response ke WWW-Authenticate header mein jaata hai.
        Isse clients samajhte hain ki kaunsa authentication expected hai.
        """
        return 'APIKey realm="api"'


# ══ PART C: Custom Permission ═════════════════════════════════════════════════

class IsOwnerOrAdmin(BasePermission):
    """
    Custom permission: Sirf owner ya admin hi access kar sake.

    has_permission: Request-level check (list, create)
    has_object_permission: Object-level check (retrieve, update, delete)
    """

    message = "You don't have permission to access this resource."

    def has_permission(self, request, view):
        """
        Called for EVERY request.
        Return True = allow, False = 403 Forbidden
        """
        # Authenticated hona chahiye
        if not request.user or not request.user.is_authenticated:
            return False
        print(f"[IsOwnerOrAdmin] has_permission: user={request.user.username}")
        return True

    def has_object_permission(self, request, view, obj):
        """
        Called for detail endpoints (pk wale).
        get_object() ke baad check hota hai.
        """
        # Admin sab kuch kar sakta hai
        if request.user.is_staff:
            return True

        # Owner check — obj.user, obj.owner, obj.created_by — model ke hisaab se
        owner = getattr(obj, 'user', None) or getattr(obj, 'owner', None)
        is_owner = owner == request.user

        print(f"[IsOwnerOrAdmin] has_object_permission: is_owner={is_owner}")
        return is_owner


# ══ PART D: Serializer Internal Flow ═════════════════════════════════════════

class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer ka dual role:
    INPUT:  to_internal_value() → validation → save() → DB
    OUTPUT: to_representation() → JSON response
    """

    # SerializerMethodField — read-only computed field
    display_price = serializers.SerializerMethodField()

    class Meta:
        # model = Product  # Apna model import karo
        # fields = ['id', 'name', 'price', 'category', 'display_price', 'created_at']
        # read_only_fields = ['id', 'created_at']
        pass

    def get_display_price(self, obj) -> str:
        """SerializerMethodField ka method — hamesha get_<field_name>"""
        return f"₹{obj.price:,.2f}"

    def to_internal_value(self, data):
        """
        INPUT SIDE — Request body → Validated Python dict.

        Kab call hota hai: serializer.is_valid() call karne pe.

        Flow:
        1. Each field ka run_validation() call hota hai
        2. Field-level validate_<field>() methods call hote hain
        3. is_valid() ke baad validate() (object-level) call hota hai
        4. Result: self.validated_data mein milta hai

        Yahan karo:
        - Raw data transform karo (type convert, normalize)
        - Custom pre-validation logic
        """
        print(f"\n[Serializer] to_internal_value() CALLED")
        print(f"  Raw input: {data}")

        # Parent ka kaam karne do (field validation, type coercion)
        validated = super().to_internal_value(data)

        # Post-processing agar chahiye
        if 'name' in validated:
            validated['name'] = validated['name'].strip().title()

        print(f"  Validated output: {validated}")
        return validated

    def to_representation(self, instance):
        """
        OUTPUT SIDE — DB object/dict → Python dict → JSON.

        Kab call hota hai: serializer.data access karne pe.

        Yahan karo:
        - Computed/derived fields add karo
        - Request context ke hisaab se fields hide karo
        - Nested data format customize karo
        - Currency format, date format, etc.
        """
        print(f"\n[Serializer] to_representation() CALLED")
        print(f"  Instance: {instance}")

        result = super().to_representation(instance)

        # Computed field add karo
        if 'price' in result:
            result['formatted_price'] = f"₹{result['price']}"
            result['is_premium'] = Decimal(str(result['price'])) > 5000

        # Request context se conditional fields
        request = self.context.get('request')
        if request and not request.user.is_staff:
            # Non-staff users ko cost price mat dikho
            result.pop('cost_price', None)
            result.pop('supplier_name', None)

        print(f"  Serialized output keys: {list(result.keys())}")
        return result

    def validate_price(self, value):
        """
        Field-level validation — to_internal_value ke BAAD call hota hai.
        validate_<field_name> pattern.
        """
        if value <= 0:
            raise serializers.ValidationError("Price must be positive")
        if value > 1_000_000:
            raise serializers.ValidationError("Price cannot exceed ₹10,00,000")
        return value

    def validate(self, attrs):
        """
        Object-level validation — sab fields validate hone ke BAAD.
        Multiple fields check karo yahan.
        """
        # Sale price must be less than regular price
        if attrs.get('sale_price') and attrs['sale_price'] >= attrs.get('price', 0):
            raise serializers.ValidationError(
                {"sale_price": "Sale price must be less than regular price"}
            )
        return attrs

    def create(self, validated_data):
        """
        serializer.save() → create() call hota hai jab instance nahi hota.
        """
        print(f"[Serializer] create() called with: {validated_data}")
        # return Product.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """
        serializer.save() → update() call hota hai jab instance hota hai.
        """
        print(f"[Serializer] update() called — updating {instance}")
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        # instance.save()
        return instance


# ══ PART E: ViewSet + Router — URL Generation Demo ═══════════════════════════

# Router automatically ye URL patterns generate karta hai:
#
# router.register('products', ProductViewSet, basename='product')
#
# URL Pattern                      Action Method     URL Name
# ─────────────────────────────────────────────────────────────
# GET    /products/               → list()          product-list
# POST   /products/               → create()        product-list
# GET    /products/{pk}/          → retrieve()      product-detail
# PUT    /products/{pk}/          → update()        product-detail
# PATCH  /products/{pk}/          → partial_update()product-detail
# DELETE /products/{pk}/          → destroy()       product-detail
# GET    /products/featured/      → featured()      product-featured
# POST   /products/{pk}/publish/  → publish()       product-publish


class ProductViewSet(viewsets.ModelViewSet):
    """
    ModelViewSet = ListModelMixin + CreateModelMixin + RetrieveModelMixin
                 + UpdateModelMixin + DestroyModelMixin + GenericViewSet

    Sab kuch automatic — bas queryset aur serializer_class dalo.
    """
    # queryset = Product.objects.select_related('category').all()
    # serializer_class = ProductSerializer
    # permission_classes = [IsAuthenticatedOrReadOnly]
    # throttle_classes = [UserRateThrottle]

    def get_queryset(self):
        """
        Dynamic queryset — request ke hisaab se filter karo.
        Class attribute queryset se ye better hai jab request.user chahiye.
        """
        qs = super().get_queryset()

        # Query param filter
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category__slug=category)

        # Current user ka data
        if self.action in ('my_products', 'update', 'partial_update', 'destroy'):
            qs = qs.filter(owner=self.request.user)

        return qs

    def get_serializer_class(self):
        """
        Different actions ke liye different serializers.
        """
        # if self.action == 'list':
        #     return ProductListSerializer  # Lightweight — few fields
        # elif self.action in ('create', 'update', 'partial_update'):
        #     return ProductWriteSerializer  # Write-oriented fields
        # return ProductDetailSerializer  # Full detail
        pass

    def perform_create(self, serializer):
        """
        create() mein serializer.save() se pehle extra data inject karo.
        """
        serializer.save(
            owner=self.request.user,
            created_ip=self.request.META.get('REMOTE_ADDR'),
        )

    @viewsets.action(detail=False, methods=['get'])
    def featured(self, request):
        """
        Custom collection-level action.
        URL: GET /products/featured/
        detail=False → collection pe, no pk needed
        """
        # featured_products = self.get_queryset().filter(is_featured=True)
        # serializer = self.get_serializer(featured_products, many=True)
        return Response({"message": "Featured products would be here"})

    @viewsets.action(detail=True, methods=['post'], url_path='publish')
    def publish(self, request, pk=None):
        """
        Custom object-level action.
        URL: POST /products/{pk}/publish/
        detail=True → specific pk chahiye
        url_path='publish' → URL mein 'publish' segment
        """
        product = self.get_object()  # get_object() permission check bhi karta hai!
        # product.is_published = True
        # product.save()
        return Response({"status": f"Product {pk} published"})
'''

print("\n[DRF INTERNALS CODE TEMPLATE]")
print("Upar ka code apne project mein copy karo. Key takeaways:")
print()
print("  dispatch() flow order:")
print("    1. initialize_request() → DRF Request wrap")
print("    2. initial()           → auth + permissions + throttle")
print("    3. get()/post()/etc.   → view method")
print()
print("  Authentication:")
print("    - None return karo → next authenticator try hoga")
print("    - (user, auth) return karo → success")
print("    - AuthenticationFailed raise karo → 401 immediately")
print()
print("  Serializer Pipeline:")
print("    INPUT:  to_internal_value() → validate_<f>() → validate() → save()")
print("    OUTPUT: to_representation() → JSON Response")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: QUICK REFERENCE — Interview Cheat Sheet
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "═"*60)
print("SECTION 5: Interview Quick Reference")
print("═"*60)

INTERVIEW_CHEATSHEET = """
┌─────────────────────────────────────────────────────────────────┐
│              DJANGO INTERNALS — QUICK REFERENCE                 │
├─────────────────────────────────────────────────────────────────┤
│ MIDDLEWARE ORDER                                                 │
│   process_request  → TOP to BOTTOM (MIDDLEWARE list order)      │
│   process_response → BOTTOM to TOP (reverse order)             │
│   process_exception → View mein exception aane pe              │
├─────────────────────────────────────────────────────────────────┤
│ SIGNALS — BUILT-IN                                              │
│   pre_save / post_save    → Model .save() se pehle/baad        │
│   pre_delete / post_delete → Model .delete() se pehle/baad     │
│   m2m_changed             → ManyToMany change pe               │
│   request_started/finished → Har HTTP request pe               │
├─────────────────────────────────────────────────────────────────┤
│ SIGNAL BEST PRACTICES                                           │
│   ✅ apps.py ready() mein register karo                        │
│   ✅ **kwargs hamesha rakho (future-proof)                     │
│   ✅ dispatch_uid use karo (double registration avoid)         │
│   ✅ transaction.on_commit ke saath Celery task queue karo     │
│   ✅ Tests mein disconnect karo (side effects avoid)           │
│   ❌ Signal mein heavy I/O mat karo (email, API calls)         │
│   ❌ Circular imports — local imports use karo                 │
├─────────────────────────────────────────────────────────────────┤
│ ASYNC DJANGO                                                    │
│   Django 3.1+: async def views                                 │
│   Django 4.1+: native async ORM (aget, acount, acreate)        │
│   sync_to_async: sync code → async context mein use           │
│   async_to_sync: async code → sync context mein use           │
│   httpx.AsyncClient: external HTTP calls (requests nahi!)     │
│   asyncio.gather: parallel async operations                    │
│   SynchronousOnlyOperation: direct ORM in async = CRASH       │
├─────────────────────────────────────────────────────────────────┤
│ DRF DISPATCH FLOW                                               │
│   as_view() → dispatch() → initialize_request() → initial()   │
│   initial() = authenticate + check_permissions + check_throttle│
│   Authentication: None=skip, (user,auth)=success, raise=401   │
│   Serializer INPUT:  to_internal_value → validate → save      │
│   Serializer OUTPUT: to_representation → JSON                  │
└─────────────────────────────────────────────────────────────────┘
"""

print(INTERVIEW_CHEATSHEET)


# ═══════════════════════════════════════════════════════════════════════════════
# RUN ALL DEMOS
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "█"*60)
    print("ALL DEMOS COMPLETE!")
    print("█"*60)
    print("""
FILES TO CREATE IN YOUR DJANGO PROJECT:
─────────────────────────────────────────
myproject/
├── middleware.py              ← Section 1: RequestLifecycleMiddleware
├── users/
│   ├── apps.py               ← Section 2: UsersConfig.ready()
│   └── signals.py            ← Section 2: All signal receivers
├── payments/
│   └── signals.py            ← Section 2: Custom payment signals
└── myapp/
    ├── views_async.py         ← Section 3: All async view patterns
    └── views_drf_internals.py ← Section 4: DRF traced views, custom auth

SETTINGS.PY MEIN ADD KARO:
─────────────────────────────
MIDDLEWARE = [
    ...
    'myproject.middleware.RequestLifecycleMiddleware',
    ...
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'myapp.views_drf_internals.APIKeyAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

INSTALLED_APPS = [
    'users.apps.UsersConfig',  # ready() method ke liye full path
    ...
]
""")
