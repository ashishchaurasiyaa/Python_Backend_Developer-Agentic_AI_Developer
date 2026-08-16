# APIs & Security Deep Guide — REST · JWT · OAuth2 · RBAC · Webhooks · Microservices
### Resume Skills: REST API Design, JWT, OAuth2, RBAC, Webhooks (HMAC), Microservices
### PwC Interview Ready · 3-4 baar padho

> **Reading plan:**
> - Pass 1: Poora padho — architecture samjho
> - Pass 2: Interview answers loud bolke practice karo
> - Pass 3: Architecture diagrams haath se draw karo
> - Pass 4: Quick Recall Card only

---

## TABLE OF CONTENTS

| # | Topic | Tera Resume Project |
|---|---|---|
| 1 | REST API Design — principles + conventions | All DRF projects |
| 2 | API Versioning + Error responses | Niroskos, YES Platform |
| 3 | JWT — structure + auth flow | All projects |
| 4 | JWT — djangorestframework-simplejwt | DRF setup |
| 5 | OAuth2 — flows + social login | Niroskos social login |
| 6 | RBAC — role-based access control | All projects |
| 7 | Webhooks + HMAC signature verification | Youngman Beta SAP |
| 8 | Microservices — when + architecture | Toofan AI gateway |
| 9 | API Security — full threat model | PwC specific |
| 10 | Interview Q&A — 20 Questions | PwC specific |
| 11 | Quick Recall Card | 1 ghanta pehle |

---

## TOPIC 1: REST API DESIGN — PRINCIPLES + CONVENTIONS

### REST — kya hai

```
REST = Representational State Transfer
Architectural style (not a protocol)
HTTP ke upar banaya jaata hai

6 CONSTRAINTS:
1. Client-Server     → UI aur backend separate
2. Stateless         → Server session nahi rakhta
                       Every request self-contained (JWT mein sab hai)
3. Cacheable         → GET responses cacheable (Cache-Control header)
4. Uniform Interface → Consistent URL + method conventions
5. Layered System    → Client ko nahi pata: proxy, LB, CDN beech mein hain
6. Code on Demand    → (Optional) Server JavaScript bhej sakta hai
```

### URL design — right way

```
RESOURCE-BASED URLS:

✅ GOOD                              ❌ BAD
───────────────────────────────      ───────────────────────────────
GET  /api/v1/bookings                GET  /api/getBookings
POST /api/v1/bookings                POST /api/createBooking
GET  /api/v1/bookings/42             GET  /api/getBooking?id=42
PUT  /api/v1/bookings/42             POST /api/updateBooking
PATCH /api/v1/bookings/42            POST /api/updateBookingPartial
DELETE /api/v1/bookings/42           POST /api/deleteBooking/42
GET  /api/v1/bookings/42/invoices    GET  /api/getInvoicesForBooking
POST /api/v1/bookings/42/cancel      POST /api/cancelBooking

RULES:
✅ Nouns, not verbs in URL (booking, not getBooking)
✅ Plural nouns (bookings, not booking)
✅ Nested: /resource/:id/sub-resource
✅ Actions as verbs at end: /bookings/42/cancel, /invoices/42/sync
✅ Lowercase, hyphens (not camelCase, not underscores in URL)
✅ Version in URL: /api/v1/

HTTP METHODS:
GET    → Read (safe, idempotent)
POST   → Create (not idempotent)
PUT    → Full replace (idempotent)
PATCH  → Partial update (idempotent)
DELETE → Delete (idempotent)
```

### HTTP status codes — kab kya

```
2xx SUCCESS:
200 OK          → GET success, PUT/PATCH success
201 Created     → POST success (include Location header with new resource URL)
202 Accepted    → Async operation queued (Celery task started)
204 No Content  → DELETE success, PUT/PATCH when no body to return

4xx CLIENT ERROR:
400 Bad Request         → Validation failed (serializer errors)
401 Unauthorized        → Not authenticated (no/invalid token)
403 Forbidden           → Authenticated but no permission (RBAC denied)
404 Not Found           → Resource doesn't exist
405 Method Not Allowed  → GET endpoint pe POST kiya
409 Conflict            → Duplicate (unique constraint)
422 Unprocessable       → Validation error (alternative to 400)
429 Too Many Requests   → Rate limited

5xx SERVER ERROR:
500 Internal Server Error → Unhandled exception
502 Bad Gateway           → Upstream service (DB, SAP) down
503 Service Unavailable   → Health check failing
504 Gateway Timeout       → Upstream timeout

RULE: 4xx = client ki galti, 5xx = server ki galti
```

### Standard response format

```python
# Consistent API responses — tera DRF setup

# SUCCESS response:
{
    "status": "success",
    "data": {
        "id": 42,
        "booking_number": "BK-2026-00042",
        "tour": "Manali Adventure 7D",
        "amount": "25000.00",
        "status": "confirmed"
    }
}

# LIST response with pagination:
{
    "status": "success",
    "data": [...],
    "meta": {
        "page": 1,
        "page_size": 20,
        "total": 142,
        "total_pages": 8,
        "next": "/api/v1/bookings?page=2",
        "previous": null
    }
}

# ERROR response (consistent format → frontend can rely on it):
{
    "status": "error",
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid booking data",
        "details": {
            "travel_date": ["Travel date must be in the future."],
            "guests": ["Maximum 20 guests per booking."]
        }
    }
}

# DRF custom exception handler:
def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        response.data = {
            "status": "error",
            "error": {
                "code": response.status_code,
                "message": str(exc),
                "details": response.data,
            }
        }
    return response

# settings.py
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "config.exceptions.custom_exception_handler"
}
```

### Filtering, sorting, pagination

```python
# DRF with django-filter

# views.py
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

class BookingViewSet(ModelViewSet):
    queryset = Booking.objects.select_related("tour", "user").all()
    serializer_class = BookingSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    # Exact filters: ?status=confirmed&tour=42
    filterset_fields = {"status": ["exact", "in"], "tour": ["exact"], "travel_date": ["gte", "lte"]}

    # Search: ?search=manali (searches across fields)
    search_fields = ["booking_number", "user__email", "tour__title"]

    # Ordering: ?ordering=-travel_date,amount
    ordering_fields = ["travel_date", "amount", "created_at"]
    ordering = ["-created_at"]   # default

# Cursor pagination (efficient for large datasets):
from rest_framework.pagination import CursorPagination

class BookingCursorPagination(CursorPagination):
    page_size = 20
    cursor_query_param = "cursor"
    ordering = "-created_at"   # stable ordering required

# Usage: GET /api/v1/bookings?status=confirmed&ordering=-travel_date
#        GET /api/v1/bookings?search=manali&page_size=10
```

---

## TOPIC 2: API VERSIONING

### Strategies

```
VERSIONING OPTIONS:
──────────────────────────────────────────────────────────────

1. URL PATH (most common, tera choice):
   /api/v1/bookings
   /api/v2/bookings
   ✅ Explicit, easy to route, browser/cache friendly
   ❌ URL mein version (some argue non-RESTful)

2. QUERY PARAMETER:
   /api/bookings?version=1
   ❌ Easy to forget, cache pollutes

3. HEADER:
   Accept: application/vnd.niroskos.v1+json
   ✅ URL clean
   ❌ Hard to test in browser, harder to document

4. SUBDOMAIN:
   v1.api.niroskos.com
   ❌ DNS management complex

MY CHOICE: URL path (/api/v1/)
Simple, explicit, easy to deprecate old versions.
```

### Django URL versioning

```python
# urls.py
from django.urls import path, include

urlpatterns = [
    path("api/v1/", include("api.v1.urls")),
    path("api/v2/", include("api.v2.urls")),
]

# api/v1/urls.py
router = DefaultRouter()
router.register("bookings", BookingViewSet, basename="booking")
urlpatterns = router.urls

# DEPRECATION STRATEGY:
# 1. Add deprecation header to v1 responses
# 2. Communicate sunset date
# 3. Monitor v1 usage (CloudWatch logs)
# 4. Remove only when v1 traffic → 0

class DeprecationMiddleware:
    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/v1/"):
            response["Deprecation"] = "true"
            response["Sunset"] = "2027-01-01"
            response["Link"] = '</api/v2/>; rel="successor-version"'
        return response
```

---

## TOPIC 3: JWT — STRUCTURE + AUTH FLOW

### What is JWT

```
JWT = JSON Web Token
Stateless authentication mechanism.
Server state nahi rakhta — token mein sab hai.
```

### JWT structure

```
JWT = header.payload.signature

EXAMPLE:
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9
  .eyJ1c2VyX2lkIjo0Miwicm9sZSI6ImFkbWluIiwiZXhwIjoxNjkxMjM0NTY3fQ
  .SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c

DECODE:
Header (base64):   {"alg": "HS256", "typ": "JWT"}
Payload (base64):  {
                     "user_id": 42,
                     "email": "ashish@example.com",
                     "role": "admin",
                     "exp": 1691234567,     ← expiry timestamp
                     "iat": 1691230967,     ← issued at
                     "jti": "abc-uuid-123"  ← unique token ID
                   }
Signature:         HMACSHA256(
                     base64(header) + "." + base64(payload),
                     SECRET_KEY           ← only server knows this
                   )

VERIFICATION:
1. Decode header + payload (anyone can read these!)
2. Recompute signature with SECRET_KEY
3. Compare with signature in token
4. If match → token valid (not tampered)
5. Check exp → not expired
6. Extract user_id → authenticate user

IMPORTANT: JWT is SIGNED, not ENCRYPTED!
Payload is readable by anyone (base64 decode).
Never put sensitive data in payload.
```

### JWT auth flow

```
JWT ACCESS + REFRESH TOKEN FLOW
────────────────────────────────────────────────────────────────

CLIENT                          DJANGO SERVER
  │                                   │
  │  POST /api/v1/auth/login/         │
  │  {email, password}               │
  │──────────────────────────────────►│
  │                                   │ Verify credentials
  │                                   │ Generate tokens:
  │                                   │  access_token (15 min)
  │                                   │  refresh_token (7 days)
  │◄──────────────────────────────────│
  │  {access_token, refresh_token}    │
  │                                   │
  │  GET /api/v1/bookings/            │
  │  Authorization: Bearer {access}  │
  │──────────────────────────────────►│
  │                                   │ Verify access_token
  │                                   │ (no DB lookup needed!)
  │◄──────────────────────────────────│
  │  {bookings data}                  │
  │                                   │
  │  (15 min later — access expired) │
  │                                   │
  │  POST /api/v1/auth/refresh/       │
  │  {refresh_token}                 │
  │──────────────────────────────────►│
  │                                   │ Verify refresh_token
  │                                   │ Check blacklist (DB lookup)
  │                                   │ Generate new access_token
  │                                   │ Rotate refresh_token (new one!)
  │                                   │ Blacklist old refresh_token
  │◄──────────────────────────────────│
  │  {new_access_token,               │
  │   new_refresh_token}              │
  │                                   │
  │  POST /api/v1/auth/logout/        │
  │  {refresh_token}                 │
  │──────────────────────────────────►│
  │                                   │ Blacklist refresh_token
  │◄──────────────────────────────────│
  │  {detail: "Logged out"}           │
```

### Token storage — security

```
WHERE TO STORE JWT (frontend):

❌ localStorage:
   - XSS attack → malicious JS reads token → stolen!
   - Simple storage, easy to implement
   - NEVER use in production with sensitive data

❌ sessionStorage:
   - Same XSS vulnerability as localStorage

✅ httpOnly Cookie (RECOMMENDED):
   - httpOnly flag → JS cannot read (XSS safe!)
   - Secure flag → HTTPS only
   - SameSite=Strict → CSRF protection
   - Browser handles automatically

Response.set_cookie(
    "access_token",
    value=access_token,
    httponly=True,    # JS cannot read
    secure=True,      # HTTPS only
    samesite="Strict" # No cross-site requests
)

✅ Memory (in-memory JS variable):
   - XSS can't persist across page reload
   - Lost on page refresh → use refresh token in httpOnly cookie
   - Best UX/security balance for SPAs
```

---

## TOPIC 4: JWT — DJANGORESTFRAMEWORK-SIMPLEJWT

### Full production setup

```python
# ══════════════════════════════════════════════════════
# INSTALL + SETUP
# ══════════════════════════════════════════════════════
# pip install djangorestframework-simplejwt

# settings.py
from datetime import timedelta

INSTALLED_APPS = [
    ...
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",  # for logout
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,      # new refresh token on each use
    "BLACKLIST_AFTER_ROTATION": True,   # old refresh → blacklisted
    "UPDATE_LAST_LOGIN": True,          # update User.last_login

    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,

    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",

    # Custom claims:
    "TOKEN_OBTAIN_SERIALIZER": "users.serializers.CustomTokenObtainPairSerializer",
}

# urls.py
from rest_framework_simplejwt.views import (
    TokenObtainPairView, TokenRefreshView, TokenBlacklistView
)

urlpatterns = [
    path("api/v1/auth/login/", TokenObtainPairView.as_view()),
    path("api/v1/auth/refresh/", TokenRefreshView.as_view()),
    path("api/v1/auth/logout/", TokenBlacklistView.as_view()),
]

# ══════════════════════════════════════════════════════
# CUSTOM TOKEN — add extra claims to payload
# ══════════════════════════════════════════════════════
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims to payload:
        token["email"] = user.email
        token["role"] = user.role   # custom field
        token["company_id"] = user.company_id
        return token

# ══════════════════════════════════════════════════════
# CUSTOM AUTHENTICATION (e.g., cookie-based)
# ══════════════════════════════════════════════════════
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # Try Authorization header first
        header = self.get_header(request)
        if header:
            return super().authenticate(request)

        # Fall back to httpOnly cookie
        raw_token = request.COOKIES.get("access_token")
        if not raw_token:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token

# ══════════════════════════════════════════════════════
# TOKEN BLACKLIST CHECK (logout all devices)
# ══════════════════════════════════════════════════════
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

class LogoutAllDevicesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Blacklist ALL outstanding tokens for this user
        tokens = OutstandingToken.objects.filter(user=request.user)
        for token in tokens:
            try:
                RefreshToken(token.token).blacklist()
            except Exception:
                pass
        return Response({"detail": "Logged out from all devices"})
```

---

## TOPIC 5: OAUTH2 — FLOWS + SOCIAL LOGIN

### OAuth2 flows — kab kya

```
OAUTH2 GRANT TYPES:

1. AUTHORIZATION CODE (with PKCE) — Web + Mobile apps
   "Login with Google" ka yahi flow hai
   Most secure, recommended for user-facing apps

2. CLIENT CREDENTIALS — Machine to machine
   Cron job, microservice → another microservice
   No user involved

3. IMPLICIT — DEPRECATED (use Authorization Code + PKCE instead)

4. PASSWORD (Resource Owner) — DEPRECATED
   User gives username/password to third-party app
   Insecure — third-party sees password
```

### Authorization Code flow — "Login with Google"

```
AUTHORIZATION CODE FLOW
────────────────────────────────────────────────────────────────

USER          NIROSKOS            GOOGLE
  │               │                  │
  │ Click         │                  │
  │ "Login        │                  │
  │  Google" ────►│                  │
  │               │ Redirect to Google Auth URL:
  │               │ https://accounts.google.com/oauth2/auth
  │               │ ?client_id=niroskos-client-id
  │               │ &redirect_uri=https://niroskos.com/callback
  │               │ &scope=openid email profile
  │               │ &state=random-csrf-token
  │               │ &code_challenge=xxx   ← PKCE
  │◄──────────────│                  │
  │ Browser → Google login page      │
  │──────────────────────────────────►
  │ User logs in, approves scopes    │
  │◄──────────────────────────────── │
  │ Redirect back to niroskos:       │
  │ /callback?code=AUTH_CODE&state=x │
  │──────────────►│                  │
  │               │ POST /oauth2/token
  │               │ {code, client_secret, code_verifier}
  │               │──────────────────►
  │               │◄──────────────────
  │               │ {access_token, id_token, refresh_token}
  │               │
  │               │ Decode id_token → {email, name, sub}
  │               │ Find or create User(email=email)
  │               │ Create JWT for Niroskos
  │◄──────────────│
  │ Niroskos JWT  │

PKCE (Proof Key for Code Exchange):
code_verifier = random string
code_challenge = base64(sha256(code_verifier))
Prevents authorization code interception attacks
```

### Social login in Django

```python
# pip install social-auth-app-django

# settings.py
INSTALLED_APPS = [
    ...
    "social_django",
]

AUTHENTICATION_BACKENDS = [
    "social_core.backends.google.GoogleOAuth2",
    "social_core.backends.github.GithubOAuth2",
    "django.contrib.auth.backends.ModelBackend",
]

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.environ.get("GOOGLE_CLIENT_ID")
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = ["openid", "email", "profile"]

# After social auth → create JWT
SOCIAL_AUTH_PIPELINE = (
    "social_core.pipeline.social_auth.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.auth_allowed",
    "social_core.pipeline.social_auth.social_user",
    "social_core.pipeline.user.get_username",
    "social_core.pipeline.user.create_user",
    "social_core.pipeline.social_auth.associate_user",
    "users.pipelines.create_jwt_token",   # custom: create JWT response
)

# users/pipelines.py
def create_jwt_token(backend, user, response, *args, **kwargs):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }

# Client credentials (machine → machine)
import requests

def get_service_token(client_id, client_secret, token_url):
    response = requests.post(token_url, data={
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "bookings:read invoices:write",
    })
    return response.json()["access_token"]

# Used by: Youngman Beta → internal reporting service
# No user involved, machine-to-machine auth
```

---

## TOPIC 6: RBAC — ROLE-BASED ACCESS CONTROL

### What is RBAC

```
RBAC = Role-Based Access Control
Users → assigned Roles → Roles → have Permissions
Don't assign permissions to users directly (hard to manage)

HIERARCHY:
USER: ashish@example.com
  └── ROLE: tour_manager
       ├── PERMISSION: bookings.view_booking
       ├── PERMISSION: bookings.change_booking
       └── PERMISSION: tours.view_tour
             (not: tours.delete_tour → only admin has this)
```

### Django permission system

```python
# ══════════════════════════════════════════════════════
# BUILT-IN DJANGO PERMISSIONS (per model)
# Auto-created: add_booking, view_booking, change_booking, delete_booking
# ══════════════════════════════════════════════════════

# Assign via admin or code:
from django.contrib.auth.models import Permission, Group

# Create groups (roles)
tour_manager = Group.objects.create(name="tour_manager")
admin = Group.objects.create(name="admin")

# Assign permissions to group
view_booking = Permission.objects.get(codename="view_booking")
change_booking = Permission.objects.get(codename="change_booking")
tour_manager.permissions.add(view_booking, change_booking)

# Assign user to group
user.groups.add(tour_manager)

# ══════════════════════════════════════════════════════
# CUSTOM PERMISSIONS
# ══════════════════════════════════════════════════════
class Booking(models.Model):
    class Meta:
        permissions = [
            ("approve_booking", "Can approve bookings"),
            ("cancel_booking", "Can cancel bookings"),
            ("export_bookings", "Can export booking data"),
        ]

# ══════════════════════════════════════════════════════
# DRF PERMISSION CLASSES
# ══════════════════════════════════════════════════════
from rest_framework.permissions import BasePermission, SAFE_METHODS

# Permission 1: Read-only for safe methods
class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_staff

# Permission 2: Role-based
class IsTourManager(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.groups.filter(name="tour_manager").exists()
        )

# Permission 3: Object-level (can only edit own bookings)
class IsBookingOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.user == request.user   # can only access own booking

# Usage in ViewSet:
class BookingViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, IsBookingOwnerOrAdmin]

    # Different permissions per action:
    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [IsAuthenticated()]
        elif self.action in ["create"]:
            return [IsAuthenticated(), IsTourManager()]
        elif self.action in ["destroy"]:
            return [IsAuthenticated(), IsAdminOrReadOnly()]
        return super().get_permissions()

# ══════════════════════════════════════════════════════
# CUSTOM ROLE MODEL (tera Niroskos setup)
# ══════════════════════════════════════════════════════
class UserRole(models.TextChoices):
    CUSTOMER = "customer", "Customer"
    GUIDE    = "guide", "Tour Guide"
    MANAGER  = "manager", "Tour Manager"
    ADMIN    = "admin", "Administrator"

class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER
    )
    company = models.ForeignKey("Company", on_delete=models.SET_NULL, null=True)

    @property
    def is_manager_or_above(self):
        return self.role in [UserRole.MANAGER, UserRole.ADMIN]

class RolePermission(BasePermission):
    role_action_map = {
        # action: [allowed roles]
        "list":     ["customer", "guide", "manager", "admin"],
        "retrieve": ["customer", "guide", "manager", "admin"],
        "create":   ["manager", "admin"],
        "update":   ["manager", "admin"],
        "destroy":  ["admin"],
        "approve":  ["manager", "admin"],
    }

    def has_permission(self, request, view):
        allowed = self.role_action_map.get(view.action, [])
        return request.user.role in allowed
```

---

## TOPIC 7: WEBHOOKS + HMAC SIGNATURE VERIFICATION

### What is a webhook

```
WEBHOOK = Reverse API
Normal: YOU call their API (polling)
Webhook: THEY call YOUR API (event-driven)

POLLING (bad):
YOUR APP                    PAYMENT GATEWAY
  │ Every 30s:                  │
  │──── "any new payments?" ───►│
  │◄─── "no" ──────────────────│
  │──── "any new payments?" ───►│
  │◄─── "no" ──────────────────│
  │──── "any new payments?" ───►│
  │◄─── "yes! INR 5000" ───────│
Wasted API calls, delayed notification

WEBHOOK (good):
YOUR APP                    PAYMENT GATEWAY
  │                              │
  │◄── POST /webhooks/payment ──│ (instant! payment event happens)
  │    {event: payment_success,  │
  │     amount: 5000, ...}       │
```

### HMAC signature — kya aur kyun

```
PROBLEM WITHOUT SIGNATURE:
Koi bhi tera /webhooks/ endpoint pe fake request bhej sakta hai:
POST /webhooks/payment
{"event": "payment_success", "amount": 999999}
→ Teri app money mark kar leti hai → fraud!

SOLUTION: HMAC-SHA256 Signature
Payment gateway har request ke saath signature attach karta hai.
Signature = HMAC(shared_secret, request_body)
Only gateway + tum same shared_secret jaante ho.

VERIFICATION:
Teri app:
1. Receive webhook request
2. Extract signature from header
3. Recompute: HMAC(OWN_SECRET, raw_body)
4. Compare: computed == received_signature
5. If match → authentic request ✅
6. If mismatch → reject 401 ❌
```

### HMAC implementation — production

```python
import hmac
import hashlib
import time
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseBadRequest

# ══════════════════════════════════════════════════════
# STRIPE-STYLE WEBHOOK VERIFICATION
# ══════════════════════════════════════════════════════
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
TIMESTAMP_TOLERANCE = 300  # 5 minutes replay window

@csrf_exempt
def stripe_webhook(request):
    # 1. Get raw body (must be raw bytes, not parsed!)
    payload = request.body
    sig_header = request.headers.get("Stripe-Signature")

    if not sig_header:
        return HttpResponseBadRequest("Missing signature")

    # Stripe signature format:
    # t=1691234567,v1=abc123def456...
    try:
        sig_parts = dict(part.split("=", 1) for part in sig_header.split(","))
        timestamp = int(sig_parts["t"])
        received_sig = sig_parts["v1"]
    except (KeyError, ValueError):
        return HttpResponseBadRequest("Invalid signature format")

    # 2. REPLAY ATTACK PREVENTION: check timestamp
    now = int(time.time())
    if abs(now - timestamp) > TIMESTAMP_TOLERANCE:
        return HttpResponseBadRequest("Request too old (replay attack?)")

    # 3. RECOMPUTE expected signature
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
    expected_sig = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    # 4. CONSTANT-TIME COMPARISON (prevent timing attacks!)
    if not hmac.compare_digest(expected_sig, received_sig):
        return HttpResponseBadRequest("Invalid signature")

    # 5. IDEMPOTENCY: prevent duplicate processing
    event_id = request.headers.get("Stripe-Event-Id")
    if WebhookEvent.objects.filter(event_id=event_id).exists():
        return HttpResponse("Already processed", status=200)

    # 6. Process event
    event = json.loads(payload)
    WebhookEvent.objects.create(event_id=event_id, processed=False)

    # Async processing (don't block webhook response!)
    process_stripe_event.delay(event)

    WebhookEvent.objects.filter(event_id=event_id).update(processed=True)
    return HttpResponse("OK", status=200)

# ══════════════════════════════════════════════════════
# CUSTOM WEBHOOK SENDER (Youngman Beta SAP style)
# ══════════════════════════════════════════════════════
def send_webhook(url: str, payload: dict, secret: str) -> bool:
    body = json.dumps(payload, sort_keys=True)   # deterministic serialization
    timestamp = str(int(time.time()))

    # Compute signature
    signed_data = f"{timestamp}.{body}"
    signature = hmac.new(
        secret.encode(),
        signed_data.encode(),
        hashlib.sha256
    ).hexdigest()

    try:
        response = requests.post(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Signature": f"t={timestamp},v1={signature}",
                "X-Event-Id": str(uuid4()),   # idempotency key
            },
            timeout=10,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        logger.error(f"Webhook delivery failed: {url} - {e}")
        return False

# RETRY WITH CELERY:
@shared_task(max_retries=5, default_retry_delay=60)
def deliver_webhook(webhook_id: int):
    webhook = Webhook.objects.get(id=webhook_id)
    success = send_webhook(webhook.url, webhook.payload, webhook.secret)
    if not success:
        raise self.retry()

# ══════════════════════════════════════════════════════
# WHY hmac.compare_digest vs == ?
# ══════════════════════════════════════════════════════
# BAD:
if expected_sig == received_sig:   # TIMING ATTACK vulnerable!
# Python == returns early on first mismatch
# Attacker can measure response time → guess correct chars one by one

# GOOD:
if hmac.compare_digest(expected_sig, received_sig):  # constant time!
# Always compares all chars regardless of where mismatch is
# No timing information leaks
```

---

## TOPIC 8: MICROSERVICES

### Monolith vs Microservices — honest comparison

```
MONOLITH (Niroskos today):
────────────────────────────────────────────────────────────────
One Django app:
├── bookings/
├── tours/
├── payments/
├── users/
├── guides/
└── reports/

All in one process, one DB, one deploy.

✅ Simple to develop (one codebase)
✅ Simple to debug (one log stream)
✅ Simple to deploy (one docker image)
✅ No network latency between "services"
✅ Easy transactions (one DB)
❌ One bug can crash everything
❌ Can't scale individual parts
❌ Tech stack locked (can't use Node for one part)
❌ Large team → merge conflicts

MICROSERVICES (Toofan AI Gateway):
────────────────────────────────────────────────────────────────
┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐
│ User Service │  │ Chat Service │  │ AI Gateway Service       │
│ (Django+PG)  │  │ (FastAPI+PG) │  │ (FastAPI+Redis)          │
└──────────────┘  └──────────────┘  └──────────────────────────┘
      │                  │                      │
      └──────────────────┴──────────────────────┘
                         │
                   Message Queue (SQS)
                   or gRPC direct calls

✅ Independent deploy (AI gateway update ≠ user service down)
✅ Independent scale (AI gateway → 20 instances, user → 2)
✅ Fault isolation (AI gateway crash → chat still works partially)
✅ Tech choice per service
❌ Distributed tracing complexity
❌ Network latency + failures (HTTP vs function call)
❌ Distributed transactions (saga pattern)
❌ Operational overhead (N services to monitor)
❌ Harder debugging (logs spread across services)
```

### When to use microservices

```
START WITH MONOLITH:
✅ <10 engineers
✅ Early product (requirements change fast)
✅ Single domain (e.g., tour booking)

BREAK INTO MICROSERVICES WHEN:
✅ Specific part needs 10x more scale than rest
   (AI inference → separate service with GPU)
✅ Independent release cycle needed
   (AI model updates weekly, core booking monthly)
✅ Different tech stack needed
   (ML in Python, analytics in Go, mobile in Kotlin)
✅ Team autonomy (50+ engineers, 5+ teams)
✅ Compliance isolation (payment data separate PCI-DSS scope)

MY EXPERIENCE:
Niroskos = Monolith (right choice for stage)
Toofan AI Gateway = Separate service
  WHY: AI/LLM calls expensive + different scaling need
       Rate limiting, cost tracking per user = own service
       Updates frequently (model changes) vs stable booking logic
```

### Service communication patterns

```
SYNCHRONOUS (request-response):
──────────────────────────────────────────────────────

REST/HTTP: Simple, human-readable, widely supported
  Service A → HTTP POST → Service B → response
  When: Low latency needed, simple CRUD, public APIs

gRPC: Google's RPC framework, Protocol Buffers, HTTP/2
  Service A → gRPC → Service B
  When: High throughput internal services, type safety, streaming
  Faster than REST (binary protocol, HTTP/2 multiplexing)

ASYNCHRONOUS (fire and forget):
──────────────────────────────────────────────────────

Message Queue (SQS/RabbitMQ):
  Service A → Queue → Service B (processes later)
  When: Non-critical operations, email/SMS, analytics

Event Bus (EventBridge/Kafka):
  Service A publishes event
  Multiple services subscribe
  When: Multiple consumers, event sourcing, audit log

WHICH WHEN (tera decision matrix):
Need immediate response? → REST/gRPC
Best effort, can be delayed? → Queue
Multiple services care about same event? → Event Bus
```

### API Gateway pattern

```
API GATEWAY PATTERN
────────────────────────────────────────────────────────────────

CLIENT (mobile/web)
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    API GATEWAY                               │
│                                                             │
│  ┌────────────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │   Auth     │  │ Rate Limit   │  │  Request routing  │   │
│  │  (JWT      │  │  (Redis)     │  │  /bookings → svc  │   │
│  │  verify)   │  │              │  │  /ai → AI svc     │   │
│  └────────────┘  └──────────────┘  └───────────────────┘   │
│                                                             │
│  ┌────────────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │  Logging   │  │  SSL Term    │  │  Response cache   │   │
│  │ (Trace ID) │  │              │  │                   │   │
│  └────────────┘  └──────────────┘  └───────────────────┘   │
└─────────────────────────────────────────────────────────────┘
    │              │                  │
    ▼              ▼                  ▼
Booking Svc   User Svc          AI Gateway

BENEFITS:
✅ Single entry point for all services
✅ Auth once, services trust gateway (internal no-auth)
✅ Rate limiting centralized
✅ SSL termination once
✅ Request logging + tracing ID injection
✅ Response caching

OPTIONS: AWS API Gateway, Kong, nginx, custom FastAPI
```

---

## TOPIC 9: API SECURITY — FULL THREAT MODEL

### OWASP API Security Top 10

```
1. BROKEN OBJECT LEVEL AUTHORIZATION (BOLA/IDOR)
   Problem: GET /api/v1/bookings/42 → can user see booking 43?
   FIX: has_object_permission() check (Topic 6)
   IsBookingOwnerOrAdmin permission always

2. BROKEN AUTHENTICATION
   Problem: Weak JWT, no expiry, no token rotation
   FIX: Short access token (15min), rotate refresh, httpOnly cookie

3. BROKEN OBJECT PROPERTY LEVEL AUTH (Mass Assignment)
   Problem: User sends {role: "admin"} in request body → promoted!
   FIX: Explicit serializer fields, never update role from user input
   BAD: User.objects.update(**request.data)  # updates any field!
   GOOD: serializer = UserSerializer(data=request.data)  # only allowed fields

4. UNRESTRICTED RESOURCE CONSUMPTION
   Problem: GET /api/v1/reports → generates 10GB file → DoS
   FIX: Rate limiting (429), pagination, max page_size, async large ops

5. BROKEN FUNCTION LEVEL AUTHORIZATION
   Problem: DELETE /api/v1/bookings/42 → non-admin can delete
   FIX: get_permissions() per action, test each endpoint with different roles

6. SENSITIVE BUSINESS FLOW ABUSE
   Problem: Bulk booking creation → inventory exhaustion
   FIX: Rate limit per user per day, business rules in application layer

7. SERVER SIDE REQUEST FORGERY (SSRF)
   Problem: POST /api/webhook-test {url: "http://169.254.169.254/"}
            (AWS metadata endpoint → credentials exposed!)
   FIX: Validate webhook URLs (block private IPs, metadata endpoints)
   import ipaddress
   def is_safe_url(url):
       parsed = urlparse(url)
       ip = socket.gethostbyname(parsed.hostname)
       addr = ipaddress.ip_address(ip)
       return not (addr.is_private or addr.is_link_local)

8. SECURITY MISCONFIGURATION
   Problem: DEBUG=True in prod, stack traces in API errors
   FIX: ALLOWED_HOSTS, DEBUG=False, custom error handler (no traceback to client)

9. IMPROPER INVENTORY MANAGEMENT
   Problem: Old v1 API still running, forgotten test endpoints
   FIX: API versioning with sunset dates, track all endpoints

10. UNSAFE API CONSUMPTION
    Problem: Third-party API response blindly trusted → injection
    FIX: Validate/sanitize all external data before use
```

### Security headers

```python
# middleware/security.py
class SecurityHeadersMiddleware:
    def __call__(self, request):
        response = self.get_response(request)
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["X-XSS-Protection"] = "1; mode=block"
        response["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response["Content-Security-Policy"] = "default-src 'self'"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

# settings.py CORS:
INSTALLED_APPS = [..., "corsheaders"]
MIDDLEWARE = ["corsheaders.middleware.CorsMiddleware", ...]
CORS_ALLOWED_ORIGINS = ["https://niroskos.com"]
CORS_ALLOW_CREDENTIALS = True  # needed for httpOnly cookie auth
# NEVER: CORS_ALLOW_ALL_ORIGINS = True in production!
```

### Rate limiting — production

```python
# DRF throttling (built-in)
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",      # unauthenticated
        "user": "1000/hour",     # authenticated
        "login": "5/minute",     # login attempts (brute force)
        "webhook": "10/minute",  # webhook delivery
    }
}

# Custom throttle for login endpoint (brute force prevention):
class LoginRateThrottle(AnonRateThrottle):
    rate = "5/minute"
    scope = "login"

class LoginView(TokenObtainPairView):
    throttle_classes = [LoginRateThrottle]

# Redis-based sliding window (Topic 10, File 10):
# More precise than DRF's fixed window
```

---

## TOPIC 10: INTERVIEW Q&A — 20 Questions

---

**Q1. REST ke 6 constraints kya hain — real example se?**

```
STATELESS (most important):
Server session nahi rakhta.
Niroskos: JWT mein user_id, role sab hai.
Server har request independently process karta hai.
Benefit: Any server can handle any request → horizontal scale.

UNIFORM INTERFACE:
/api/v1/bookings → GET list, POST create
/api/v1/bookings/42 → GET one, PUT update, DELETE
Consistent → frontend/mobile client predictable behavior.

CLIENT-SERVER:
Django API ↔ React frontend separate.
Mobile app same API use kar sakta hai.

CACHEABLE:
GET /api/v1/tours → Cache-Control: public, max-age=300
CDN (CloudFront) cache karta hai → same request DB nahi jaata.

LAYERED:
Client ko pata nahi: ALB → ECS → Django.
Add Redis cache layer → client same experience.

CODE ON DEMAND (optional):
Server JavaScript bhej sakta hai (rarely used in APIs).
```

---

**Q2. 401 vs 403 — difference kya hai?**

```
401 UNAUTHORIZED:
"Main jaanta nahi tum kaun ho."
Token nahi hai, token expired, token invalid.
Client ke response: "Please login first."
WWW-Authenticate header attach hota hai.

403 FORBIDDEN:
"Main jaanta hoon tum kaun ho, but permission nahi hai."
Token valid hai, user authenticated hai,
but RBAC → this role can't access this resource.
Client ke response: "You don't have permission for this."

REAL EXAMPLE (Niroskos):
GET /api/v1/bookings/42 with no token → 401
GET /api/v1/bookings/42 with customer token (not owner) → 403
GET /api/v1/bookings/42 with owner token → 200

COMMON BUG:
DRF returns 403 for unauthenticated requests by default!
(if no permission class includes AllowAny)
FIX:
REST_FRAMEWORK = {
    "UNAUTHENTICATED_USER": None
}
Or check authentication first in custom permission.
```

---

**Q3. JWT refresh token rotation kyu zaroori hai?**

```
WITHOUT ROTATION:
Refresh token stolen → attacker forever logged in!
Even if user changes password → old refresh works!

WITH ROTATION (ROTATE_REFRESH_TOKENS=True):
Old refresh → sends to /auth/refresh/ → new access + new refresh
Old refresh → BLACKLISTED immediately

If attacker steals refresh token:
User uses it first → new refresh issued, old blacklisted
Attacker tries with old → 401 (blacklisted!)

OR attacker uses first → user tries → 401 (blacklisted!)
→ User knows something wrong → re-login → password change

BLACKLIST:
Table: rest_framework_simplejwt_blacklisted_tokens
Stores jti (JWT ID) of blacklisted tokens
Every refresh → DB check (one extra query but worth it)

MY SETUP (Niroskos):
ACCESS_TOKEN_LIFETIME = 15 minutes (short → less damage if stolen)
REFRESH_TOKEN_LIFETIME = 7 days
ROTATE_REFRESH_TOKENS = True
BLACKLIST_AFTER_ROTATION = True
```

---

**Q4. HMAC webhook verification mein timing attack kya hai?**

```
TIMING ATTACK:
Attacker wrong signature bhejta hai.
== operator first mismatch pe return karta hai.

"abc123" == "abc999":
  a==a ✓
  b==b ✓
  c==c ✓
  1==9 ✗ → return False (took 4 comparisons)

"xyz999" == "abc999":
  x==a ✗ → return False (took 1 comparison!)

Different timing → attacker measures response time
→ guesses correct prefix byte by byte

FIX: hmac.compare_digest()
Always compares ALL characters regardless of where mismatch
→ constant time → no timing information leaks

ADDITIONAL PROTECTION:
Timestamp check (TIMESTAMP_TOLERANCE = 300 seconds)
→ Replay attack prevention
Even if attacker captures valid signed request
→ after 5 minutes → rejected

Idempotency key (X-Event-Id header):
Same event processed twice? Second → skip
```

---

**Q5. OAuth2 Authorization Code vs Client Credentials — kab kya?**

```
AUTHORIZATION CODE:
When: User-facing action, user consent needed
User grants permission to third-party
"Login with Google" → user approves → Google gives code → exchange for token

NIROSKOS EXAMPLE:
User "Login with Google" → Authorization Code flow
→ Google redirects to /callback?code=xxx
→ Exchange code for access + id token
→ Decode id_token → email, name
→ Find/create User → issue Niroskos JWT

CLIENT CREDENTIALS:
When: Machine-to-machine, no user involved
Background service authenticates itself

YOUNGMAN BETA EXAMPLE:
SAP HANA connector (backend service) → internal reporting API
→ No user → Client Credentials
POST /oauth/token {grant_type: client_credentials, client_id, client_secret}
→ {access_token: "...", expires_in: 3600}

NEVER MIX:
Don't use Client Credentials where user action needed
Don't do Authorization Code for machine-to-machine
```

---

**Q6. Mass assignment vulnerability kya hai — DRF mein kaise rokein?**

```
VULNERABILITY:
User registration API:
POST /api/v1/users/register
{
  "email": "hacker@evil.com",
  "password": "pass123",
  "role": "admin",        ← user yeh nahi bhej sakta!
  "is_staff": true        ← ya yeh!
}

BAD CODE:
User.objects.create(**request.data)   # creates admin user!

DRF PROTECTION (serializer whitelist):
class UserRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["email", "password", "first_name", "last_name"]
        # role, is_staff, is_superuser — NOT in fields!
        # Even if sent in request → ignored!
        extra_kwargs = {
            "password": {"write_only": True}
        }

    def create(self, validated_data):
        # Only validated fields available here
        user = User.objects.create_user(**validated_data)
        user.role = UserRole.CUSTOMER   # always set default, never from input
        user.save()
        return user

LESSON: Always whitelist allowed fields in serializer.
Never use read_only_fields=[...] as security measure — only style.
```

---

**Q7. API rate limiting kaise implement kiya Toofan mein?**

```
TOOFAN AI GATEWAY — rate limiting critical kyunki:
Each AI call = real money (tokens cost)
Without limit → one user exhaust entire OpenAI budget!

MULTI-LEVEL RATE LIMITING:

Level 1: IP-based (unauthenticated)
  100 requests/hour per IP
  Redis sliding window (Topic 10)

Level 2: User-based (authenticated)
  Free tier: 20 AI queries/day
  Pro tier: 500 AI queries/day

Level 3: Token budget
  Free: 10,000 tokens/day
  Pro: 500,000 tokens/day

IMPLEMENTATION:
async def check_rate_limit(user_id: int, tokens_needed: int):
    daily_key = f"usage:{user_id}:{date.today()}"
    current = r.get(daily_key) or 0
    limit = get_user_token_limit(user_id)

    if int(current) + tokens_needed > limit:
        raise RateLimitExceeded(f"Daily limit {limit} tokens exceeded")

    pipe = r.pipeline()
    pipe.incrby(daily_key, tokens_needed)
    pipe.expire(daily_key, 86400)   # reset daily
    pipe.execute()

Headers in response:
X-RateLimit-Limit: 10000
X-RateLimit-Remaining: 3456
X-RateLimit-Reset: 1691270400
```

---

**Q8. Microservices mein distributed transactions kaise handle karte ho?**

```
PROBLEM:
Booking create karo → payment deduct karo → email bhejo
3 different services!

If payment fails → booking rollback karna hai
But DB transactions cross-service nahi hote!

SOLUTION: SAGA PATTERN

CHOREOGRAPHY-BASED SAGA:
Service A → emit event → Service B reacts → emit event → Service C reacts

Booking Svc: BookingCreated event emit
Payment Svc: BookingCreated → PaymentProcessed event emit
Email Svc:   PaymentProcessed → send confirmation

COMPENSATION (rollback):
If Payment fails → PaymentFailed event emit
Booking Svc: PaymentFailed → cancel booking → BookingCancelled event
Email Svc: BookingCancelled → send cancellation email

ORCHESTRATION-BASED SAGA (simpler):
Central orchestrator tells each service what to do:
1. → Booking Svc: reserve_booking
2. → Payment Svc: charge_payment
3. If fail: → Booking Svc: cancel_reservation (compensate)

MY EXPERIENCE:
Niroskos: Monolith → Django transaction.atomic() handles everything
Toofan: Simple 2-service: AI Gateway + Main App → events via SQS
Real distributed saga → complexity not worth it at this scale
```

---

**Q9. CORS kya hai aur kaise configure kiya?**

```
CORS = Cross-Origin Resource Sharing
Browser security feature: "Can website A make requests to website B?"

PROBLEM:
https://niroskos.com (frontend) → https://api.niroskos.com (backend)
Different origins! Browser blocks by default.

PREFLIGHT REQUEST:
Browser: OPTIONS /api/v1/bookings
         Origin: https://niroskos.com
         Access-Control-Request-Method: POST

Server: Access-Control-Allow-Origin: https://niroskos.com
        Access-Control-Allow-Methods: GET, POST, PUT, DELETE
        Access-Control-Max-Age: 86400   (cache preflight)

Browser: OK, now I'll send the actual POST

DJANGO CORS SETUP:
pip install django-cors-headers

CORS_ALLOWED_ORIGINS = [
    "https://niroskos.com",
    "https://app.niroskos.com",
    # never: "*" in production with credentials
]
CORS_ALLOW_CREDENTIALS = True   # for cookies (JWT httpOnly)
CORS_ALLOW_HEADERS = [
    "authorization",
    "content-type",
    "x-csrftoken",
]
CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]

SECURITY:
❌ CORS_ALLOW_ALL_ORIGINS = True + CORS_ALLOW_CREDENTIALS = True
= Any site can make authenticated requests → CSRF equivalent attack
✅ Explicit CORS_ALLOWED_ORIGINS only
```

---

**Q10. API idempotency key kya hai?**

```
PROBLEM:
POST /api/v1/bookings → network timeout → client retries → duplicate booking!

SOLUTION: Idempotency Key
Client sends unique key per request:
POST /api/v1/bookings
Idempotency-Key: bk-user42-2026-08-15-uuid

Server:
1. Check if key already processed
2. If yes → return cached response (don't execute again!)
3. If no → process + cache result with key

IMPLEMENTATION:
class IdempotencyMiddleware:
    def __call__(self, request):
        if request.method not in ("POST", "PUT", "PATCH"):
            return self.get_response(request)

        key = request.headers.get("Idempotency-Key")
        if not key:
            return self.get_response(request)

        cache_key = f"idempotency:{request.user.id}:{key}"

        # Check cache
        cached = cache.get(cache_key)
        if cached:
            return JsonResponse(cached, status=200)

        # Process
        response = self.get_response(request)

        # Cache for 24 hours (if success)
        if 200 <= response.status_code < 300:
            cache.set(cache_key, response.data, timeout=86400)

        return response

USE CASES:
Payment processing: charge only once
Booking creation: one booking per user action
Invoice generation: one invoice per request
```

---

## QUICK RECALL CARD

```
╔══════════════════════════════════════════════════════════════════╗
║  REST · JWT · OAuth2 · RBAC · WEBHOOKS · MICROSERVICES          ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  REST                                                            ║
║  Stateless = no server session, JWT has everything              ║
║  Nouns in URL = /bookings not /getBookings                      ║
║  HTTP methods = GET(read) POST(create) PUT(replace) PATCH(part) ║
║  401 = not authenticated, 403 = authenticated but forbidden     ║
║  202 = async accepted, 409 = conflict, 429 = rate limited       ║
║  Versioning = URL path (/api/v1/)                               ║
║                                                                  ║
║  JWT                                                             ║
║  Structure = header.payload.signature (base64 encoded)          ║
║  Payload readable (NOT encrypted) — no sensitive data!          ║
║  Access token = 15 min short, Refresh = 7 days                 ║
║  ROTATE_REFRESH_TOKENS = True (theft protection)               ║
║  BLACKLIST_AFTER_ROTATION = True                                ║
║  httpOnly cookie = XSS safe storage                             ║
║  hmac.compare_digest = constant time (timing attack fix)        ║
║                                                                  ║
║  OAuth2                                                          ║
║  Authorization Code = user-facing (Login with Google)           ║
║  Client Credentials = machine-to-machine (no user)             ║
║  PKCE = code_verifier + code_challenge (mobile security)        ║
║                                                                  ║
║  RBAC                                                            ║
║  User → Group/Role → Permission (not user→permission direct)   ║
║  has_object_permission = row-level (BOLA prevention)            ║
║  get_permissions() per action = different rules per endpoint    ║
║  Mass assignment = whitelist fields in serializer               ║
║                                                                  ║
║  WEBHOOKS                                                        ║
║  HMAC-SHA256 = shared secret + body → signature                 ║
║  hmac.compare_digest = constant time comparison                 ║
║  Timestamp check = replay attack prevention (5 min window)      ║
║  Idempotency key = process event only once                      ║
║  Async processing = queue event, return 200 immediately         ║
║                                                                  ║
║  MICROSERVICES                                                   ║
║  Start with monolith → break when pain justifies complexity     ║
║  Sync = REST/gRPC, Async = Queue/EventBridge                    ║
║  API Gateway = auth + rate limit + routing in one place         ║
║  SAGA = distributed transaction (compensating transactions)     ║
║                                                                  ║
║  SECURITY (OWASP API Top 10)                                     ║
║  BOLA = has_object_permission on every object endpoint          ║
║  Auth = short token, rotation, blacklist, httpOnly cookie       ║
║  Mass assignment = whitelist serializer fields                  ║
║  Rate limit = Redis sliding window + DRF throttle               ║
║  SSRF = validate webhook URLs (block private IPs)               ║
║  CORS = explicit origins only, never *                          ║
║                                                                  ║
║  TERA RESUME:                                                    ║
║  All projects → JWT (simplejwt), DRF permissions               ║
║  Niroskos    → OAuth2 social login, RBAC roles                  ║
║  Youngman    → HMAC webhook verification (SAP events)           ║
║  Toofan      → Multi-level rate limiting, AI gateway            ║
╚══════════════════════════════════════════════════════════════════╝
```

---

*Last updated: 2026-08-15 · PwC Interview 2026-08-18*
*Resume skills: REST · JWT · OAuth2 · RBAC · Webhooks (HMAC) · Microservices*