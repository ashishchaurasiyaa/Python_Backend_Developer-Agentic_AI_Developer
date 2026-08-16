# Frameworks Deep Guide — Django · DRF · FastAPI
### Resume Skills: Django, Django REST Framework, FastAPI
### PwC Interview Ready · 3-4 baar padho

> **Reading plan:**
> - Pass 1: Poora padho — definition → example → architecture samjho
> - Pass 2: Interview Answer sections loud bolke practice karo
> - Pass 3: Architecture diagrams haath se draw karo
> - Pass 4: Quick Recall Card only

---

## TABLE OF CONTENTS

| # | Topic | Tera Resume Project |
|---|---|---|
| 1 | Django — Core Architecture | Youngman Beta, Niroskos, CRM Platform |
| 2 | Django REST Framework (DRF) | Niroskos APIs, YES Platform |
| 3 | FastAPI | Toofan gateway, AI services |
| 4 | Django vs FastAPI — kab kya | Decision framework |
| 5 | Interview Q&A — 15 Questions | PwC specific |
| 6 | Quick Recall Card | 1 ghanta pehle |

---

## TOPIC 1: DJANGO

### Definition
```
Django = Python ka "batteries-included" web framework.
2005 mein banaya — newspaper publishing ke liye.
ORM, Admin, Auth, Forms, Templates — sab built-in.
Principle: "Don't Repeat Yourself" (DRY) + "Convention over Configuration"
```

### Simple Example (analogy)
```
DJANGO vs FASTAPI analogy:

Django = Ready-made furnished flat
  Move in karo — furniture, AC, geyser sab hai
  Customize karo as needed
  Jaldi shuru karo

FastAPI = Empty flat with best-in-class fittings
  Tujhe furnish karna padega
  Exactly jo chahiye woh lagao
  More work upfront, more control

DJANGO SWEET SPOT:
✅ CRUD-heavy applications (ERP, CRM, SaaS)
✅ Admin panel needed (Odoo-style)
✅ Traditional server-side rendering
✅ Rapid prototyping
✅ Large team (conventions = consistency)
```

### Django Architecture — MTV pattern

```
DJANGO MTV ARCHITECTURE
(Model - Template - View, not MVC)
────────────────────────────────────────────────────────

BROWSER REQUEST
      │
      ▼
┌─────────────────────────────────────────────────────┐
│                   DJANGO PROJECT                     │
│                                                      │
│  urls.py  ──► routes to correct View                │
│  (URL Router)                                        │
│       │                                              │
│       ▼                                              │
│  View (views.py)  ──► business logic                │
│  (Controller in MVC)                                 │
│       │              │                               │
│       │              ▼                               │
│       │         Model (models.py)                    │
│       │         ORM → PostgreSQL/MySQL               │
│       │         migrations, relationships            │
│       │                                              │
│       ▼                                              │
│  Template (.html)   ──► rendered HTML               │
│  (View in MVC)          OR JSON (DRF)               │
└─────────────────────────────────────────────────────┘
      │
      ▼
RESPONSE TO BROWSER
```

### Django Project structure — production layout

```
myproject/                          ← Django project root
├── manage.py                       ← CLI commands
├── config/                         ← project config app
│   ├── settings/
│   │   ├── base.py                 ← common settings
│   │   ├── local.py                ← dev overrides
│   │   └── production.py           ← prod settings
│   ├── urls.py                     ← root URL routing
│   ├── wsgi.py                     ← WSGI server entry
│   └── asgi.py                     ← ASGI (async) entry
│
├── apps/
│   ├── users/                      ← custom user app
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── serializers.py          ← DRF
│   │   ├── admin.py
│   │   └── migrations/
│   │
│   ├── invoicing/                  ← business domain app
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── services.py             ← business logic (fat models/thin views)
│   │   ├── tasks.py                ← Celery tasks
│   │   └── migrations/
│   │
│   └── crm/
│
├── requirements/
│   ├── base.txt
│   └── production.txt
└── docker-compose.yml
```

### Django ORM — deep dive

```python
# ═══════════════════════════════════════════════════════
# MODELS — database table definition
# ═══════════════════════════════════════════════════════
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Invoice(models.Model):
    # Fields
    invoice_number = models.CharField(max_length=50, unique=True, db_index=True)
    amount         = models.DecimalField(max_digits=12, decimal_places=2)
    status         = models.CharField(
        max_length=20,
        choices=[
            ("draft",   "Draft"),
            ("pending", "Pending"),
            ("paid",    "Paid"),
            ("overdue", "Overdue"),
        ],
        default="draft",
        db_index=True  # filter by status → index chahiye
    )
    created_by     = models.ForeignKey(User, on_delete=models.PROTECT,
                                        related_name="invoices")
    company        = models.ForeignKey("Company", on_delete=models.CASCADE,
                                        related_name="invoices")
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "invoicing_invoice"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),  # composite index
            models.Index(fields=["company", "status"]),
        ]

    def __str__(self):
        return f"INV-{self.invoice_number} ({self.status})"

    # Business logic method (fat model pattern)
    def mark_paid(self):
        if self.status != "pending":
            raise ValueError(f"Cannot mark {self.status} invoice as paid")
        self.status = "paid"
        self.save(update_fields=["status", "updated_at"])

# ═══════════════════════════════════════════════════════
# ORM QUERIES — common patterns
# ═══════════════════════════════════════════════════════

# Basic CRUD
invoice = Invoice.objects.create(
    invoice_number="INV-001",
    amount=50000,
    status="draft",
    created_by=user,
    company=company
)

# Filter + select_related (avoids N+1)
invoices = Invoice.objects.filter(
    status="pending",
    company__name="Ashish Corp"   # JOIN via FK
).select_related(
    "created_by",    # 1 query for invoice + user (JOIN)
    "company"
).prefetch_related(
    "line_items"     # separate query, but efficient (N+1 fix)
)

# Aggregate
from django.db.models import Sum, Count, Avg

stats = Invoice.objects.filter(status="paid").aggregate(
    total_revenue=Sum("amount"),
    count=Count("id"),
    avg_amount=Avg("amount")
)

# F expressions (atomic update — no race condition)
from django.db.models import F

Invoice.objects.filter(id=invoice.id).update(
    amount=F("amount") + 1000   # DB-level add, not Python-level
)

# Q objects (complex OR/AND queries)
from django.db.models import Q

Invoice.objects.filter(
    Q(status="pending") | Q(status="overdue"),
    amount__gte=10000,
    created_at__date=datetime.date.today()
)

# Annotation (computed field)
from django.db.models import ExpressionWrapper, DurationField
from django.utils import timezone

Invoice.objects.annotate(
    age_days=ExpressionWrapper(
        timezone.now() - F("created_at"),
        output_field=DurationField()
    )
).filter(age_days__gt=timedelta(days=30))

# Raw SQL (when ORM not enough)
Invoice.objects.raw("""
    SELECT i.*, c.name as company_name
    FROM invoicing_invoice i
    JOIN companies c ON i.company_id = c.id
    WHERE i.amount > %s
""", [50000])
```

### N+1 problem — tera 60% latency reduction ka basis

```
N+1 PROBLEM:
────────────────────────────────────────────────────────

BAD (N+1 queries):
invoices = Invoice.objects.filter(status="pending")  # Query 1
for invoice in invoices:
    print(invoice.company.name)    # Query 2,3,4...N (one per invoice!)

If 100 invoices → 101 database queries!

GOOD (select_related):
invoices = Invoice.objects.filter(
    status="pending"
).select_related("company")    # 1 JOIN query instead of N
for invoice in invoices:
    print(invoice.company.name)    # no extra query — already loaded

HOW TO DETECT:
from django.db import connection
print(len(connection.queries))    # count queries

# Or: Django Debug Toolbar in dev
# Or: pgBadger for production logs
```

### Middleware — Django request/response cycle

```
HTTP REQUEST
    │
    ▼
MIDDLEWARE STACK (each runs in order):
┌─────────────────────────────────────────────────────┐
│  SecurityMiddleware      (HTTPS, HSTS, XSS headers) │
│       │                                              │
│  SessionMiddleware       (session cookie)            │
│       │                                              │
│  CommonMiddleware        (URL normalization)         │
│       │                                              │
│  CsrfViewMiddleware      (CSRF protection)           │
│       │                                              │
│  AuthenticationMiddleware (request.user set)         │
│       │                                              │
│  [Your Custom Middleware] (logging, rate limiting)   │
└─────────────────────────────────────────────────────┘
    │
    ▼
URL ROUTER → VIEW → Response
    │
    ▼
MIDDLEWARE STACK (reverse order on response)
    │
    ▼
HTTP RESPONSE

# Custom middleware example
class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import time, logging
        start = time.time()

        response = self.get_response(request)   # call next middleware/view

        duration = (time.time() - start) * 1000
        logging.info(f"{request.method} {request.path} "
                     f"{response.status_code} {duration:.1f}ms")
        return response
```

### Celery + Django (async tasks)

```python
# tasks.py
from celery import shared_task
from django.core.mail import send_mail

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # retry after 60s
    autoretry_for=(Exception,),
)
def send_invoice_email(self, invoice_id: int):
    """Send invoice email — runs in background worker."""
    try:
        invoice = Invoice.objects.select_related("company").get(id=invoice_id)
        send_mail(
            subject=f"Invoice {invoice.invoice_number}",
            message=f"Amount: {invoice.amount}",
            from_email="billing@company.com",
            recipient_list=[invoice.company.email]
        )
    except Exception as exc:
        raise self.retry(exc=exc)

# views.py — trigger async
def create_invoice(request):
    invoice = Invoice.objects.create(...)
    send_invoice_email.delay(invoice.id)   # non-blocking!
    return JsonResponse({"id": invoice.id})
```

### Tera project connection

```
YOUNGMAN BETA (Operations & Invoicing):
────────────────────────────────────────
Django models: Invoice, PurchaseOrder, Challan, CreditNote
ORM optimization: select_related on invoice → company → SAP HANA sync
Celery tasks: async SAP HANA push, email notifications
Result: Rs 50 Crore+ annually, 10,000+ invoices/month

NIROSKOS SAFARIS:
─────────────────
Django 5.2: multi-tenant (subdomain routing)
9 core modules built from scratch
State machine for bookings (DRAFT → CONFIRMED → PAID → CANCELLED)

CRM PLATFORM (Odoo):
────────────────────
57+ custom Odoo modules = Django apps on Odoo framework
Same ORM patterns, same signal/hook concepts
```

### Interview Answer

> **Q: "Django mein N+1 problem kya hai aur tune kaise fix kiya?"**
>
> *"N+1 problem tab hota hai jab ek query se N records aate hain aur phir
> har record ke liye ek aur query execute hoti hai — total N+1 queries.
> Mere case mein invoice list page pe 100 invoices fetch hote the, aur
> har invoice ke liye company naam alag query se aata tha — 101 queries
> per request. Fix: select_related use kiya — Django ek JOIN query mein
> invoice aur company dono fetch karta hai. p95 latency 60% reduce hui.
> Detection ke liye Django Debug Toolbar use kiya dev mein aur production
> mein slow query log se Django queries profile kiye."*

---

## TOPIC 2: DJANGO REST FRAMEWORK (DRF)

### Definition
```
DRF = Django REST Framework.
Django ke upar REST API banane ka standard library.
Serializers, ViewSets, Routers, Authentication — sab provide karta hai.
```

### Simple Example
```
WITHOUT DRF:                         WITH DRF:
──────────────────────────           ──────────────────────────
def invoice_list(request):           class InvoiceViewSet(ModelViewSet):
    if request.method == "GET":          queryset = Invoice.objects.all()
        data = list(Invoice              serializer_class = InvoiceSerializer
               .objects.values())
        return JsonResponse(data,    # Auto: GET list, GET detail,
                           safe=False)   POST create, PUT update,
    elif request.method == "POST":       PATCH partial, DELETE
        ...parse manually...
        Invoice.objects.create(...)  # Auto: pagination, filtering,
        ...                              auth, permissions, throttling
50 lines of boilerplate          5 lines → full REST API
```

### DRF Architecture — layers

```
DRF ARCHITECTURE
────────────────────────────────────────────────────────

HTTP Request
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  AUTHENTICATION (who is this?)                      │
│  - SessionAuthentication (browser)                  │
│  - TokenAuthentication (mobile/API)                 │
│  - JWTAuthentication (djangorestframework-simplejwt)│
│  - CustomAuthentication                             │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  PERMISSIONS (can they do this?)                    │
│  - IsAuthenticated                                  │
│  - IsAdminUser                                      │
│  - IsOwnerOrReadOnly (custom)                       │
│  - DjangoModelPermissions (model-level)             │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  THROTTLING (rate limiting)                         │
│  - AnonRateThrottle: 100/day                        │
│  - UserRateThrottle: 1000/day                       │
│  - CustomThrottle: per endpoint                     │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  VIEW / VIEWSET (business logic)                    │
│  - APIView (full control)                           │
│  - GenericAPIView (mixins)                          │
│  - ModelViewSet (full CRUD)                         │
│  - ReadOnlyModelViewSet (list + retrieve only)      │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
┌──────────────────┐  ┌────────────────────┐
│  SERIALIZER      │  │  QUERYSET          │
│  (validation +   │  │  (filter, order,   │
│   data in/out)   │  │   paginate)        │
└──────────────────┘  └────────────────────┘
              │
              ▼
         RESPONSE (JSON)
```

### Serializers — core of DRF

```python
from rest_framework import serializers
from .models import Invoice, Company

# ═══════════════════════════════════════════════════════
# MODEL SERIALIZER (most common)
# ═══════════════════════════════════════════════════════
class InvoiceSerializer(serializers.ModelSerializer):
    # Read-only computed field
    company_name = serializers.CharField(
        source="company.name",
        read_only=True
    )
    # Nested serializer
    line_items = LineItemSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "invoice_number", "amount", "status",
            "company_name", "line_items", "created_at"
        ]
        read_only_fields = ["id", "created_at"]

    # Custom validation
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive")
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        if attrs.get("status") == "paid" and not attrs.get("payment_date"):
            raise serializers.ValidationError(
                {"payment_date": "Required when marking as paid"}
            )
        return attrs

    def create(self, validated_data):
        """Custom create — set created_by from request."""
        request = self.context["request"]
        validated_data["created_by"] = request.user
        return super().create(validated_data)

# ═══════════════════════════════════════════════════════
# VIEWSET — full CRUD in ~10 lines
# ═══════════════════════════════════════════════════════
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "company"]
    ordering_fields = ["amount", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Users see only their company's invoices."""
        return Invoice.objects.filter(
            company=self.request.user.company
        ).select_related("company", "created_by").prefetch_related("line_items")

    # Custom action (non-standard endpoint)
    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request, pk=None):
        """POST /api/invoices/{id}/mark-paid/"""
        invoice = self.get_object()
        try:
            invoice.mark_paid()
            return Response({"status": "paid"})
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

# ═══════════════════════════════════════════════════════
# ROUTER — auto URL generation
# ═══════════════════════════════════════════════════════
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register("invoices", InvoiceViewSet, basename="invoice")

# Auto-generated URLs:
# GET  /api/invoices/          → list
# POST /api/invoices/          → create
# GET  /api/invoices/{id}/     → retrieve
# PUT  /api/invoices/{id}/     → update
# PATCH /api/invoices/{id}/    → partial_update
# DELETE /api/invoices/{id}/   → destroy
# POST /api/invoices/{id}/mark-paid/ → custom action
```

### JWT Authentication — production setup

```python
# settings.py
INSTALLED_APPS = ["rest_framework_simplejwt", ...]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": "100/hour",
    },
    "DEFAULT_PAGINATION_CLASS":
        "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

from datetime import timedelta
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":  timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,     # new refresh on each use
    "BLACKLIST_AFTER_ROTATION": True,  # old token invalidated
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# urls.py
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView,
)

urlpatterns = [
    path("auth/login/",   TokenObtainPairView.as_view()),
    path("auth/refresh/", TokenRefreshView.as_view()),
    path("auth/logout/",  TokenBlacklistView.as_view()),
    path("api/", include(router.urls)),
]
```

### Tera project connection

```
NIROSKOS SAFARIS:
─────────────────
DRF ViewSets for: Packages, Bookings, Payments, Destinations, CMS
JWT auth for mobile app + web frontend
Custom permissions: IsOwnerOrReadOnly for packages
Pagination: PageNumberPagination for package listing

YES PLATFORM:
──────────────
DRF + RBAC for certificate generation endpoints
OTP authentication flow (custom auth class)
1000+ certificates/month, sub-200ms p95

YOUNGMAN BETA:
──────────────
Internal APIs: invoice create, status update, SAP sync webhook
HMAC webhook verification (Exotel callbacks)
```

### Interview Answer

> **Q: "DRF mein authentication aur authorization kaise implement kiya?"**
>
> *"Niroskos mein simplejwt use kiya — access token 15 min, refresh 7 days,
> rotation with blacklisting on logout. Authorization ke liye: global
> IsAuthenticated default rakkha, object-level permissions custom likhe —
> package owner hi edit kar sakta hai, read all ke liye allow. RBAC ke
> liye DjangoModelPermissions use kiya admin actions pe — invoice approve
> karne ka permission alag tha mark_paid se. YES Platform mein OTP-based
> custom authentication class likhi — token 10 min expire, single use,
> redis mein store karke validate kiya."*

---

## TOPIC 3: FASTAPI

### Definition
```
FastAPI = Modern Python web framework for building APIs.
2019 mein banaya — async-first, type hints based, auto-docs.
Starlette pe based + Pydantic validation.
Python frameworks mein fastest — async/await native support.
```

### Simple Example (analogy)
```
DJANGO = Full-featured car (sedan) — everything included
DRF    = Sports car attachment on sedan — API on top of Django
FASTAPI = Sports car built from scratch — API-first, async-native

FASTAPI SWEET SPOT:
✅ High-performance APIs (async database, HTTP calls)
✅ AI/ML model serving (inference endpoints)
✅ Microservices (lightweight, no Django overhead)
✅ Real-time (WebSocket, SSE, streaming)
✅ Auto documentation (Swagger UI built-in)
✅ Type safety (Pydantic everywhere)
```

### FastAPI Architecture

```
FASTAPI ARCHITECTURE
────────────────────────────────────────────────────────

HTTP Request
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  STARLETTE (ASGI framework underneath FastAPI)       │
│  - Request/Response objects                         │
│  - Middleware stack                                  │
│  - WebSocket support                                 │
│  - Static files                                     │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  FASTAPI LAYER                                       │
│  - Route matching (@app.get, @app.post, etc.)       │
│  - Dependency Injection (Depends())                 │
│  - Pydantic validation (request body, query params) │
│  - Response model validation                        │
│  - OpenAPI schema generation (auto Swagger UI)      │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  YOUR ROUTE HANDLER (async function)                │
│  - async def → runs in event loop (non-blocking)   │
│  - sync def  → runs in threadpool (blocking OK)    │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
┌──────────────────┐  ┌──────────────────┐
│  PYDANTIC        │  │  SQLALCHEMY       │
│  (validation +   │  │  (async ORM)      │
│   serialization) │  │  OR httpx         │
└──────────────────┘  │  (external APIs)  │
                       └──────────────────┘
```

### Core FastAPI concepts — code

```python
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional, List
import asyncio

app = FastAPI(
    title="Toofan AI Gateway",
    version="1.0.0",
    description="Multi-agent orchestration API"
)

# ═══════════════════════════════════════════════════════
# PYDANTIC MODELS — request/response validation
# ═══════════════════════════════════════════════════════
class AgentRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000,
                       description="User query for the agent")
    session_id: Optional[str] = None
    tools: List[str] = Field(default=["search", "database"])

    @validator("query")
    def query_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Query cannot be whitespace only")
        return v.strip()

class AgentResponse(BaseModel):
    result: str
    tools_used: List[str]
    tokens_used: int
    session_id: str

# ═══════════════════════════════════════════════════════
# DEPENDENCY INJECTION — shared resources
# ═══════════════════════════════════════════════════════
from anthropic import AsyncAnthropic

async def get_claude_client() -> AsyncAnthropic:
    """Injected into routes that need Claude."""
    return AsyncAnthropic()

async def get_db():
    """Async DB session (SQLAlchemy)."""
    async with AsyncSessionLocal() as session:
        yield session   # FastAPI closes after request

async def verify_api_key(
    api_key: str = Header(..., alias="X-API-Key")
) -> str:
    """Authentication dependency."""
    if api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

# ═══════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════
@app.post(
    "/api/v1/agent/run",
    response_model=AgentResponse,
    tags=["Agent"],
    summary="Run agentic workflow"
)
async def run_agent(
    request: AgentRequest,
    background_tasks: BackgroundTasks,
    claude: AsyncAnthropic = Depends(get_claude_client),
    db = Depends(get_db),
    api_key: str = Depends(verify_api_key),  # auth
):
    """Run multi-agent workflow with Claude."""
    try:
        # Main work — async, non-blocking
        result = await process_with_agent(claude, request.query, request.tools)

        # Background task — runs after response sent
        background_tasks.add_task(
            log_usage,
            session_id=request.session_id,
            tokens=result.tokens_used
        )

        return AgentResponse(
            result=result.text,
            tools_used=result.tools_called,
            tokens_used=result.tokens_used,
            session_id=request.session_id or generate_session_id()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════
# STREAMING — SSE for real-time agent output
# ═══════════════════════════════════════════════════════
from fastapi.responses import StreamingResponse
import json

@app.post("/api/v1/agent/stream")
async def stream_agent(
    request: AgentRequest,
    claude: AsyncAnthropic = Depends(get_claude_client),
):
    """Stream agent tokens as SSE."""

    async def generate():
        async with claude.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": request.query}]
        ) as stream:
            async for text in stream.text_stream:
                # SSE format
                yield f"data: {json.dumps({'token': text})}\n\n"

        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Nginx buffering disable
        }
    )

# ═══════════════════════════════════════════════════════
# MIDDLEWARE
# ═══════════════════════════════════════════════════════
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://toofan.aiportfolio.co.in"],
    allow_methods=["*"],
    allow_headers=["*"],
)

import time
from starlette.middleware.base import BaseHTTPMiddleware

class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = (time.time() - start) * 1000
        response.headers["X-Process-Time"] = f"{duration:.1f}ms"
        return response

app.add_middleware(TimingMiddleware)

# ═══════════════════════════════════════════════════════
# LIFESPAN — startup/shutdown
# ═══════════════════════════════════════════════════════
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP: connections initialize karo
    await database.connect()
    await redis_client.ping()
    print("App started — DB and Redis connected")

    yield  # app runs here

    # SHUTDOWN: cleanup karo
    await database.disconnect()
    await redis_client.close()
    print("App shutting down — connections closed")

app = FastAPI(lifespan=lifespan)
```

### Async vs Sync — critical concept

```python
# ══════════════════════════════════════════════════════
# async def → event loop mein run hota hai
# ══════════════════════════════════════════════════════
@app.get("/async-example")
async def async_route():
    # ✅ GOOD: await async operations
    result = await async_db_query()      # non-blocking
    response = await httpx.get(url)      # non-blocking
    return {"data": result}

# ══════════════════════════════════════════════════════
# sync def → threadpool mein run hota hai (FastAPI handles)
# ══════════════════════════════════════════════════════
@app.get("/sync-example")
def sync_route():
    # ✅ OK: sync DB (psycopg2, not async)
    result = db.query(Invoice).all()
    return {"data": result}

# ══════════════════════════════════════════════════════
# THE TRAP — blocking in async
# ══════════════════════════════════════════════════════
@app.get("/bad-example")
async def bad_route():
    # ❌ WRONG: sync blocking operation in async route
    time.sleep(5)                        # blocks event loop!
    result = requests.get(url)           # blocks event loop!

    # ✅ FIX: use async alternatives
    await asyncio.sleep(5)               # non-blocking
    async with httpx.AsyncClient() as c:
        result = await c.get(url)        # non-blocking
```

### FastAPI for AI services — Toofan pattern

```
TOOFAN ARCHITECTURE (FastAPI gateway):
────────────────────────────────────────────────────────

CLIENT (React / mobile app)
      │
      │  HTTP / WebSocket
      ▼
FASTAPI GATEWAY (Port 8000)
├── POST /api/v1/agent/run      → LangGraph workflow
├── POST /api/v1/agent/stream   → SSE streaming
├── GET  /api/v1/sessions/{id}  → conversation history
└── WS   /ws/agent/{session_id} → real-time WebSocket
      │
      │  Depends() injection
      ▼
┌────────────────────────────────────────────────────┐
│  SERVICES                                          │
│  ├── LangGraph agent (Claude + tools)             │
│  ├── MCP client (3 custom servers)                │
│  ├── Redis (session state, rate limiting)         │
│  └── PostgreSQL (conversation history)            │
└────────────────────────────────────────────────────┘
```

### Tera project connection

```
TOOFAN PROJECT:
────────────────
FastAPI = gateway for multi-agent system
SSE streaming: real-time token output to frontend
Background tasks: usage logging, session cleanup
Depends(): Claude client, DB session, API key auth

AI LOG ANALYSIS SERVER:
────────────────────────
FastAPI endpoints expose MCP server results as REST API
/api/logs/search, /api/logs/errors, /api/logs/timeline
```

### Interview Answer

> **Q: "FastAPI aur Django mein kya choose karoge aur kyun?"**
>
> *"Use case pe depend karta hai — dono use kiye hain. Django main tab
> choose karta hoon jab: CRUD-heavy app hai, admin panel chahiye, large
> team hai (conventions consistency laate hain), ya rapid prototyping
> chahiye — Youngman Beta aur Niroskos Django pe hain.
> FastAPI tab jab: async performance matter karta hai, AI/ML model
> serving hai, ya microservice hai with tight latency requirements —
> Toofan ka AI gateway FastAPI pe hai kyunki async Claude API calls
> aur SSE streaming chahiye tha. Django mein blocking code likha hota
> to event loop block hoti. Practically: backend ERP = Django,
> AI inference API = FastAPI."*

---

## TOPIC 4: DJANGO vs FastAPI — DECISION FRAMEWORK

```
REQUIREMENT                    DJANGO + DRF    FASTAPI
──────────────────────────     ────────────    ─────────
Built-in Admin panel           ✅ YES          ❌ Manual
ORM (batteries included)       ✅ YES          ⚠️ SQLAlchemy
Async-first                    ⚠️ Partial      ✅ YES
Performance (high RPS)         ⚠️ OK           ✅ Better
Auto Swagger docs              ⚠️ drf-yasg      ✅ Built-in
Type safety                    ⚠️ Partial       ✅ Pydantic native
WebSocket / SSE                ⚠️ Channels      ✅ Native
ML/AI model serving            ❌ Overkill      ✅ Perfect
Existing team knows Django     ✅ Faster ramp   ❌ Learning curve
Large CRUD application         ✅ Better        ⚠️ More boilerplate
Microservice (small, focused)  ❌ Too heavy     ✅ Lightweight
```

### When to use both together

```
PRODUCTION ARCHITECTURE (tera company ka pattern):

┌─────────────────────────────────────────────────────┐
│  DJANGO MONOLITH (main application)                 │
│  - ERP: Invoicing, CRM, Operations                  │
│  - Admin panel for internal team                    │
│  - Complex ORM queries                              │
│  - Celery background tasks                          │
└──────────────────────┬──────────────────────────────┘
                       │  Internal API calls
                       ▼
┌─────────────────────────────────────────────────────┐
│  FASTAPI MICROSERVICE (AI features)                 │
│  - Claude agent API                                 │
│  - Log analysis service                             │
│  - Real-time streaming                              │
│  - High-performance endpoints                       │
└─────────────────────────────────────────────────────┘
```

---

## TOPIC 5: INTERVIEW Q&A — 15 Questions

---

**Q1. Django ORM vs raw SQL — kab kya use karte ho?**

```
ORM use karo (90% cases):
✅ CRUD operations (create, read, update, delete)
✅ Relationships (FK, M2M, select_related)
✅ Aggregations (Sum, Count, Avg)
✅ Safe from SQL injection (parameterized)
✅ Database-agnostic (switch PostgreSQL → MySQL)

Raw SQL use karo (10% cases):
✅ Complex window functions (ORM support limited)
✅ Database-specific features (PostgreSQL JSONB ops)
✅ Performance-critical query (ORM adds overhead)
✅ Reporting queries (multiple JOINs, CTEs)

My approach: ORM first. If EXPLAIN ANALYZE shows
suboptimal plan, raw SQL. Always parameterized —
never string concatenation (SQL injection risk).
```

---

**Q2. Django migrations ka flow kya hai?**

```
models.py change kiya (new field ya model)
         │
         ▼
python manage.py makemigrations
         │  Generates: 0002_invoice_add_gst_number.py
         │  (snapshot of model state)
         ▼
python manage.py migrate
         │  Runs SQL: ALTER TABLE invoicing_invoice ADD COLUMN gst_number...
         ▼
Database updated

PRODUCTION SAFE MIGRATION TIPS:
✅ Add nullable columns (no table lock)
✅ Never delete column — first remove from code, deploy, then delete
✅ Large tables: use django-pg-zero-downtime (concurrent index creation)
✅ Test on staging with prod data volume first
✅ Rollback plan: squash migrations, data migration reversal

DANGEROUS:
❌ Adding NOT NULL column without default on large table (full table lock!)
❌ Renaming column (Django thinks: delete old + add new)
```

---

**Q3. DRF Serializer vs Django Form — kya difference hai?**

```
Django Form:
- HTML form se data validate karta hai
- POST data (multipart) handle karta hai
- Template rendering ke liye

DRF Serializer:
- JSON data validate karta hai (API input)
- Nested objects handle karta hai (FK, M2M)
- Both directions: validate input AND format output
- ModelSerializer: model se auto-generate fields

USE:
Web app (browser form) → Django Form
REST API (JSON in/out)  → DRF Serializer
```

---

**Q4. FastAPI Depends() kya hai — teri real use case?**

```
Depends() = Dependency Injection in FastAPI.
Shared resource ek baar define karo, multiple routes mein inject karo.

PATTERN:
async def get_db() → yields DB session
async def verify_token() → validates JWT
async def get_current_user(db=Depends(get_db), token=Depends(verify_token))

MERI USE CASE (Toofan):
- get_claude_client() → singleton Claude client
- get_db() → async SQLAlchemy session (context managed)
- verify_api_key() → header se key validate karo
- rate_limiter() → Redis se rate limit check

BENEFIT:
✅ DRY — logic ek jagah, har route mein inject
✅ Testable — mock dependencies in tests
✅ Composable — dependencies chain karo
✅ Auto cleanup — yield wale Depends context manager jaisa
```

---

**Q5. Django signals kya hain — tune kahan use kiye?**

```
Signal = event system. Kuch happen hone pe automatically trigger.
Observer pattern Django mein.

BUILT-IN SIGNALS:
pre_save / post_save     → model save ke before/after
pre_delete / post_delete → model delete ke before/after
request_started / finished → HTTP request lifecycle
m2m_changed              → ManyToMany change

MERI USE CASE (Niroskos):
@receiver(post_save, sender=Booking)
def send_confirmation_email(sender, instance, created, **kwargs):
    if created and instance.status == "confirmed":
        send_booking_confirmation.delay(instance.id)  # Celery

MERI USE CASE (Youngman Beta):
@receiver(post_save, sender=Invoice)
def sync_to_sap(sender, instance, **kwargs):
    if instance.status == "paid":
        push_to_sap_hana.delay(instance.id)  # async Celery task

SIGNAL PITFALLS:
⚠️ Post_save runs in same transaction — exception = rollback
⚠️ Signals don't run with bulk_update() — use update() sparingly
⚠️ Hard to debug — hidden side effects
✅ Better: explicit service layer call in view (more obvious)
```

---

**Q6. FastAPI mein authentication kaise implement kiya?**

```
JWT AUTH FLOW (Toofan):

1. Login endpoint:
   POST /auth/login {email, password}
   → verify credentials
   → generate JWT (access: 15min, refresh: 7days)
   → return tokens

2. Protected route:
   GET /api/agent/history
   Header: Authorization: Bearer <access_token>
   → Depends(verify_token) extracts + validates JWT
   → request.user = decoded payload

3. Refresh:
   POST /auth/refresh {refresh_token}
   → validate refresh token (Redis blacklist check)
   → new access token return

CODE:
from jose import jwt, JWTError
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def verify_token(credentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=["HS256"]
        )
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

---

**Q7. Django mein multi-tenancy kaise implement ki? (Niroskos)**

```
MULTI-TENANCY APPROACHES:
1. Separate DB per tenant (isolation ++ , cost --)
2. Shared DB, schema per tenant (PostgreSQL schemas)
3. Shared DB, shared schema + tenant_id column (simplest)

NIROSKOS APPROACH: Option 3 + subdomain routing

SUBDOMAIN ROUTING:
client1.niroskos.com → request → middleware
middleware reads: request.get_host() → "client1"
                 → looks up tenant by subdomain
                 → sets request.tenant

TENANT MIDDLEWARE:
class TenantMiddleware:
    def __call__(self, request):
        subdomain = request.get_host().split(".")[0]
        try:
            request.tenant = Tenant.objects.get(subdomain=subdomain)
        except Tenant.DoesNotExist:
            return HttpResponse("Unknown tenant", status=404)
        return self.get_response(request)

MODEL FILTERING:
Every queryset filtered by tenant:
class TenantManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(
            tenant=local_tenant.get()   # thread-local ya contextvars
        )
```

---

**Q8. FastAPI async database — kaise use karte ho?**

```python
# SQLAlchemy 2.0 async
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/db"
engine = create_async_engine(DATABASE_URL, pool_size=10)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@app.get("/invoices/{id}")
async def get_invoice(id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Invoice).where(Invoice.id == id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404)
    return invoice

# WHY ASYNC DB:
# Sync DB in async route → blocks event loop → bad
# Async DB in async route → non-blocking → good
# For high-concurrency: async = 10x more throughput
```

---

**Q9. Django caching strategy — tune kahan use kiya?**

```
DJANGO CACHE LEVELS:
────────────────────────────────────────────
Level 1: Per-view cache         (coarsest)
Level 2: Template fragment cache
Level 3: Low-level cache API    (finest)

MY USE CASE (Youngman Beta):
from django.core.cache import cache

# SAP HANA auth token cache (avoids re-auth on every request)
def get_sap_token():
    token = cache.get("sap_hana_token")
    if not token:
        token = sap_authenticate()
        cache.set("sap_hana_token", token, timeout=3500)  # 58 min (token valid 60min)
    return token

# Redis as cache backend (production)
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://localhost:6379/1",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "TIMEOUT": 300,   # 5 min default
    }
}
```

---

**Q10. DRF pagination — kaise implement kiya?**

```python
# settings.py
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# Custom pagination (cursor-based for large datasets)
class InvoiceCursorPagination(CursorPagination):
    page_size = 50
    ordering = "-created_at"  # must be unique, indexed field
    cursor_query_param = "cursor"

class InvoiceViewSet(ModelViewSet):
    pagination_class = InvoiceCursorPagination

# Response format:
{
    "count": 10000,
    "next": "https://api.example.com/invoices/?cursor=abc123",
    "previous": null,
    "results": [...]
}

# CURSOR vs PAGE NUMBER:
# PageNumber: page=1, page=2 — simple, but slow on large offset
# Cursor: encoded position — O(log n), consistent with new inserts
# Large dataset (10k+ records) → cursor pagination
```

---

**Q11. Django queryset lazy evaluation — kya matlab?**

```python
# Queryset LAZY — SQL nahi chali ab tak
invoices = Invoice.objects.filter(status="pending")  # no SQL yet
invoices = invoices.select_related("company")         # no SQL yet
invoices = invoices.order_by("-created_at")           # no SQL yet

# EVALUATION happens here (SQL finally runs):
for invoice in invoices:       # iterate karo
    print(invoice.company.name)

# ya
list(invoices)                 # list() se evaluate
invoices[0]                    # slice se
invoices.count()               # count se
invoices.exists()              # exists se

# WHY LAZY?
# Chain filters karo efficiently — ek SQL mein sab
# Premature DB call avoid hoti hai
```

---

**Q12. FastAPI error handling — production mein?**

```python
from fastapi import Request
from fastapi.responses import JSONResponse

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log karo (with trace_id for correlation)
    logger.error(f"Unhandled error: {exc}", exc_info=True,
                 extra={"trace_id": request.headers.get("X-Trace-ID")})
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "Something went wrong",
            "trace_id": request.headers.get("X-Trace-ID")
        }
    )

# Custom exception
class InvoiceNotFoundError(Exception):
    def __init__(self, invoice_id: int):
        self.invoice_id = invoice_id

@app.exception_handler(InvoiceNotFoundError)
async def invoice_not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "not_found", "invoice_id": exc.invoice_id}
    )
```

---

**Q13. Django admin — production mein kaise secure kiya?**

```
DEFAULT RISKS:
/admin/ URL publicly accessible
No brute force protection
No 2FA

PRODUCTION HARDENING:
1. URL change karo:
   path("secret-admin-url/", admin.site.urls)

2. IP restriction (nginx level):
   location /secret-admin-url/ {
       allow 10.0.0.0/8;  # internal only
       deny all;
   }

3. django-admin-honeypot:
   /admin/ → fake admin → logs attacker IP

4. 2FA: django-two-factor-auth

5. django-axes: brute force detection (N failed attempts → lockout)

MY APPROACH (Youngman Beta):
- Custom URL + IP allowlist via nginx
- Admin only from VPN
- Separate admin user (not superuser for daily use)
```

---

**Q14. Toofan mein FastAPI ka SSE streaming kaise kiya?**

```
SSE = Server-Sent Events
Server → Client one-directional streaming
(vs WebSocket = bidirectional)

WHEN TO USE SSE:
✅ LLM token streaming (user dekhta hai tokens aate hue)
✅ Progress updates (file processing 20%... 40%... done)
✅ Live notifications (one-way)
❌ Chat app (WebSocket better — bidirectional)

IMPLEMENTATION:
@app.post("/api/v1/agent/stream")
async def stream_agent(request: AgentRequest):
    async def generate():
        async with claude.messages.stream(...) as stream:
            async for text in stream.text_stream:
                yield f"data: {json.dumps({'token': text})}\n\n"
                await asyncio.sleep(0)   # yield control to event loop
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

FRONTEND (JavaScript):
const source = new EventSource("/api/v1/agent/stream");
source.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.done) source.close();
    else appendToken(data.token);
};
```

---

**Q15. Django vs FastAPI performance — numbers?**

```
BENCHMARK (approximate, varies by hardware):

FRAMEWORK              RPS (simple JSON endpoint)
──────────────────     ────────────────────────────
FastAPI (async)        ~30,000 RPS
Django + DRF (sync)    ~5,000 RPS
Django + DRF (async)   ~15,000 RPS
Flask                  ~4,000 RPS

WHY FASTAPI FASTER:
1. Async I/O — event loop, no thread blocking
2. Pydantic v2 (Rust-based) — fast validation
3. Starlette — lightweight ASGI framework
4. No template engine overhead (API only)

REAL WORLD CAVEAT:
DB query = bottleneck in most cases
Async DB (asyncpg) + connection pooling = biggest gain
Framework overhead = small portion of total request time

MY ANSWER:
"For CPU-bound work, difference small hai. For I/O-bound
(DB, external API) — FastAPI async significantly better.
Toofan mein async Claude API calls + async Redis + async DB
= FastAPI clear winner. Youngman Beta mein sync Django fine
hai — bottleneck DB queries hain, framework nahi."
```

---

## QUICK RECALL CARD

```
╔════════════════════════════════════════════════════════════════╗
║           DJANGO + DRF + FASTAPI RECALL CARD                  ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  DJANGO                                                        ║
║  Pattern  = MTV (Model-Template-View)                         ║
║  ORM      = models.py → migrations → DB                       ║
║  N+1 fix  = select_related (FK) / prefetch_related (M2M)      ║
║  Signals  = post_save, pre_delete (observer pattern)          ║
║  Celery   = @shared_task, .delay() for async                  ║
║  Caching  = django-redis, cache.get/set                       ║
║  Admin    = secure: custom URL + IP allowlist + 2FA           ║
║  Project  = Youngman Beta (Rs 50Cr), Niroskos, CRM            ║
║                                                                ║
║  DRF                                                           ║
║  Core     = Serializer → View/ViewSet → Router → Response     ║
║  Auth     = simplejwt (access 15min, refresh 7d, rotate)      ║
║  Perms    = IsAuthenticated, IsOwnerOrReadOnly (custom)        ║
║  ViewSet  = ModelViewSet → auto CRUD + @action for custom     ║
║  Filter   = DjangoFilterBackend + filterset_fields            ║
║  Paginate = PageNumber (simple) / Cursor (large dataset)      ║
║  Project  = Niroskos APIs, YES Platform certs                 ║
║                                                                ║
║  FASTAPI                                                       ║
║  Base     = Starlette (ASGI) + Pydantic (validation)          ║
║  async    = async def + await = non-blocking                  ║
║  sync     = sync def = threadpool (Django ORM safe)           ║
║  Depends  = Dependency Injection (DB, auth, Claude client)    ║
║  SSE      = StreamingResponse + async generator               ║
║  Auth     = HTTPBearer + jose jwt.decode                      ║
║  Lifespan = startup/shutdown (DB connect/disconnect)          ║
║  Project  = Toofan AI gateway, Log Analysis Server            ║
║                                                                ║
║  DJANGO vs FASTAPI:                                            ║
║  CRUD + Admin + Large team = Django                           ║
║  AI/ML serving + Async + Microservice = FastAPI               ║
║  Both used together = production pattern                      ║
╚════════════════════════════════════════════════════════════════╝
```

---

*Last updated: 2026-08-15 · PwC Interview 2026-08-18*
*Resume skills: Django · DRF · FastAPI*