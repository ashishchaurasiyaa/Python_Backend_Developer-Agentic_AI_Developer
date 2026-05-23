# Django Multi-Tenant Architecture & API Documentation
## Phase 2 — Interview Prep (Hinglish Style)

---

## SECTION A — Multi-Tenant Architecture

### Concept Samajhte Hain Pehle

```
SaaS = Multiple companies (tenants) same app use karte hain
Example: Slack — har company ka alag workspace
         Notion — har team ka alag workspace
         Shopify — har shop ka alag store

Multi-tenancy matlab:
  - Ek hi codebase deploy hai
  - Har company (tenant) ko lagta hai unka apna system hai
  - Data completely isolated rehta hai
  - Resources (server, DB) share hote hain → cost efficient
```

---

### 3 Approaches — Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Approach 1: Shared DB, Shared Schema                           │
│  → Ek hi database, ek hi tables, sirf tenant_id column alag     │
│                                                                  │
│  Approach 2: Shared DB, Separate Schema                         │
│  → Ek hi database, PostgreSQL schemas alag-alag (most popular) │
│                                                                  │
│  Approach 3: Separate DB per Tenant                             │
│  → Har tenant ka completely alag database                       │
└─────────────────────────────────────────────────────────────────┘
```

---

### Approach 1 — Shared DB, Shared Schema (Simplest)

**Concept:** Har table mein ek `tenant_id` column hota hai. Sab kuch ek jagah, sirf filter alag.

```python
# Har model mein tenant_id
class TenantAwareModel(models.Model):
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE)
    
    class Meta:
        abstract = True

class Product(TenantAwareModel):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # Automatically tenant_id column aayega yahan


# -------------------------------------------------------
# Tenant Middleware — request se tenant identify karo
# -------------------------------------------------------
class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Subdomain se tenant identify karo
        # company1.myapp.com → tenant = company1
        host = request.get_host()   # "company1.myapp.com"
        subdomain = host.split('.')[0]   # "company1"
        
        try:
            tenant = Tenant.objects.get(subdomain=subdomain, is_active=True)
            request.tenant = tenant   # Request pe lagao, baad mein use karo
        except Tenant.DoesNotExist:
            return HttpResponse("Tenant not found", status=404)
        
        return self.get_response(request)


# -------------------------------------------------------
# Custom Manager — always filter by tenant automatically
# -------------------------------------------------------
class TenantManager(models.Manager):
    def get_queryset(self):
        from threading import local
        _thread_locals = local()
        tenant = getattr(_thread_locals, 'current_tenant', None)
        qs = super().get_queryset()
        if tenant:
            return qs.filter(tenant=tenant)
        return qs
```

**Key Points:**
- `TenantAwareModel` → abstract base class, sab models isse inherit karein
- Middleware → request mein `tenant` attribute inject karo
- Custom Manager → queries automatically tenant ke liye filter hon

---

### Approach 2 — Schema-per-Tenant (django-tenants library)

**Concept:** PostgreSQL ke built-in schema feature use karo. Har tenant ka alag schema → `company1.products`, `company2.products`.

```python
# pip install django-tenants

# ===== settings.py =====
DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']
TENANT_MODEL = "tenants.Tenant"
TENANT_DOMAIN_MODEL = "tenants.Domain"

# Shared data (har tenant ke liye same) vs Tenant-specific data
SHARED_APPS = [
    'django_tenants',        # Library khud
    'tenants',               # Tenant model
    'django.contrib.auth',   # Auth shared rahegi
    'django.contrib.contenttypes',
]

TENANT_APPS = [
    'products',   # Har tenant ka alag products table
    'orders',     # Har tenant ka alag orders table
    'users',      # Tenant-specific users
]

INSTALLED_APPS = SHARED_APPS + TENANT_APPS


# ===== models.py =====
from django_tenants.models import TenantMixin, DomainMixin

class Tenant(TenantMixin):
    name = models.CharField(max_length=100)
    created_on = models.DateField(auto_now_add=True)
    auto_create_schema = True   # Tenant banao → schema automatically banega

class Domain(DomainMixin):
    # company1.myapp.com → Tenant ke saath link
    pass


# ===== Migrations =====
# python manage.py migrate_schemas --shared   # Pehli baar public schema banao
# python manage.py migrate_schemas            # Sab schemas mein migrate karo

# Naya tenant create karo
tenant = Tenant(schema_name='company1', name='Company One')
tenant.save()   # PostgreSQL schema "company1" automatically ban jayega

domain = Domain(domain='company1.myapp.com', tenant=tenant, is_primary=True)
domain.save()
```

**How it works internally:**
```
PostgreSQL mein:
  public schema      → Tenant model, Domain model, shared data
  company1 schema    → Products, Orders, Users (only for company1)
  company2 schema    → Products, Orders, Users (only for company2)

Request aaya company1.myapp.com →
  django-tenants middleware schema set karta hai "company1" →
  Sab queries automatically company1 schema se hoti hain →
  Data leakage impossible!
```

---

### Approach 3 — Separate DB per Tenant

**Concept:** Enterprise clients ke liye — har tenant ka completely alag database. Maximum isolation.

```python
# ===== Database Router =====
class TenantDatabaseRouter:
    """Har query ko sahi database pe route karo"""
    
    def db_for_read(self, model, **hints):
        tenant = get_current_tenant()
        if tenant:
            return f"tenant_{tenant.id}"   # "tenant_5" database use karo
        return "default"
    
    def db_for_write(self, model, **hints):
        tenant = get_current_tenant()
        if tenant:
            return f"tenant_{tenant.id}"
        return "default"
    
    def allow_relation(self, obj1, obj2, **hints):
        # Sirf same database ke objects ke beech relation allow karo
        db_set = {"default", "tenant_1", "tenant_2"}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return True


# ===== settings.py — dynamic databases =====
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "shared_db",
        "HOST": "localhost",
    },
    "tenant_1": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "tenant_1_db",
        "HOST": "dedicated-server-1.example.com",   # Alag server bhi ho sakta
    },
    "tenant_2": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "tenant_2_db",
        "HOST": "dedicated-server-2.example.com",
    },
}

DATABASE_ROUTERS = ['myapp.routers.TenantDatabaseRouter']
```

---

### Comparison Table

```
┌─────────────────────────────────────────────────────────────────┐
│ Approach          │ Pros                  │ Cons                │
├─────────────────────────────────────────────────────────────────┤
│ Shared Schema     │ Simple, cheap         │ Data leakage risk   │
│ (tenant_id col)   │ Easy queries          │ No schema isolation │
│                   │ Fast to build         │ Large tables        │
│                   │ Any SQL DB works      │ Row-level security  │
│                   │                       │ manually manage     │
├─────────────────────────────────────────────────────────────────┤
│ Schema per Tenant │ Good isolation        │ Complex migrations  │
│ (django-tenants)  │ PostgreSQL native     │ Schema limit ~10k   │
│                   │ Easy per-tenant backup│ More complex setup  │
│                   │ Best balance          │ PostgreSQL only     │
├─────────────────────────────────────────────────────────────────┤
│ DB per Tenant     │ Full isolation        │ Most expensive      │
│                   │ Custom scaling        │ Complex management  │
│                   │ Compliance-ready      │ Many DB connections │
│                   │ Dedicated resources   │ Hard to query across│
└─────────────────────────────────────────────────────────────────┘

Kab choose karein:
  Startup/Small    → Shared Schema (fastest to build, cheapest)
  Mid-size SaaS    → Schema per Tenant (best balance of isolation + cost)
  Enterprise/HIPAA → DB per Tenant (compliance required, premium clients)
```

---

### Interview Questions — Multi-Tenant Architecture

**Q1. Multi-tenancy ke 3 approaches explain karo aur kab kaunsa choose karenge?**

**A:**
```
Multi-tenancy matlab ek hi application instance se multiple organizations ko serve karna.

1. Shared Schema (tenant_id column):
   - Simplest approach — har table mein tenant_id FK
   - Middleware se tenant identify karo, Custom Manager se filter
   - Risk: Ek galat query sabka data expose kar sakti hai
   - Best for: Startups, MVP, budget constraints

2. Schema per Tenant (django-tenants):
   - PostgreSQL schemas use karo — company1.products, company2.products
   - django-tenants library handle karta hai automatically
   - Schema-level isolation — accidental leakage much harder
   - Best for: Mid-size SaaS, when PostgreSQL available

3. Separate DB per Tenant:
   - Har tenant ka alag database, alag server bhi possible
   - Maximum isolation — HIPAA, GDPR, financial compliance ke liye
   - Multiple Django database routers use karo
   - Best for: Enterprise clients, regulatory compliance

Production mein main Schema per Tenant choose karta — good isolation + manageable cost.
```

---

**Q2. Tenant Middleware kaise kaam karta hai? Data leakage kaise rokein?**

**A:**
```
Tenant Middleware workflow:

Request aaya (company1.myapp.com/api/products/) →
  Middleware: host se subdomain nikalo → "company1" →
  DB lookup: Tenant.objects.get(subdomain="company1") →
  request.tenant = tenant object →
  View/ViewSet: request.tenant automatically milta hai

Data Leakage Prevention (Defense in Depth):

1. Custom Manager (Model level):
   class TenantManager(models.Manager):
       def get_queryset(self):
           tenant = get_current_tenant()
           return super().get_queryset().filter(tenant=tenant)

2. TenantFilterMixin (ViewSet level):
   def get_queryset(self):
       return Product.objects.filter(tenant=self.request.tenant)

3. perform_create override:
   def perform_create(self, serializer):
       serializer.save(tenant=self.request.tenant)  # Force correct tenant

4. Unit tests for cross-tenant access:
   - Company A ka user Company B ka data access na kar sake
   - Ye explicitly test karo

Multiple layers hona zaroori hai — sirf ek layer pe depend mat karo.
```

---

**Q3. django-tenants library ka `SHARED_APPS` vs `TENANT_APPS` kya hota hai?**

**A:**
```
PostgreSQL mein do types ke schemas hote hain:

PUBLIC schema (shared):
  - SHARED_APPS ke models yahan migrate hote hain
  - django.contrib.auth, contenttypes — sab tenants share karte hain
  - Tenant model khud yahan hota hai
  - Koi bhi tenant access kar sakta hai

TENANT schemas (e.g., company1, company2):
  - TENANT_APPS ke models yahan migrate hote hain
  - Products, Orders — tenant-specific data
  - Har tenant ka completely alag copy

Example:
  SHARED_APPS = ['django_tenants', 'tenants', 'django.contrib.auth']
  TENANT_APPS = ['products', 'orders']

  public.auth_user → Shared users
  company1.products_product → Company 1 ke products
  company2.products_product → Company 2 ke products

Migration command:
  python manage.py migrate_schemas --shared   # Sirf public schema
  python manage.py migrate_schemas            # Sab tenant schemas update
```

---

**Q4. Tenant onboarding kaise automate karein? (New company signup)**

**A:**
```python
# Naya tenant register hone pe automatically sab setup ho jaye
from django_tenants.models import TenantMixin

def onboard_new_tenant(company_name, subdomain, admin_email):
    """
    New company signup pe call karo.
    1. Tenant record banao
    2. Domain link karo
    3. PostgreSQL schema auto-create hoga (auto_create_schema=True)
    4. Admin user banao tenant ke context mein
    """
    from django.db import transaction
    
    with transaction.atomic():
        # Step 1: Tenant banao
        tenant = Tenant.objects.create(
            schema_name=subdomain,   # PostgreSQL schema name
            name=company_name,
        )
        
        # Step 2: Domain link karo
        Domain.objects.create(
            domain=f"{subdomain}.myapp.com",
            tenant=tenant,
            is_primary=True,
        )
        
        # Step 3: Tenant ke context mein admin user banao
        from django_tenants.utils import schema_context
        with schema_context(subdomain):
            User.objects.create_superuser(
                username='admin',
                email=admin_email,
                password=generate_secure_password(),
            )
    
    # Welcome email bhejo
    send_welcome_email(admin_email, subdomain)
    
    return tenant

# Isme auto_create_schema=True hone se django-tenants
# automatically PostgreSQL schema bana deta hai tenant.save() pe.
```

---

## SECTION B — API Documentation with drf-spectacular

### Setup — Basic Configuration

```python
# pip install drf-spectacular

# ===== settings.py =====
INSTALLED_APPS = [
    ...
    'drf_spectacular',    # Ye add karo
]

REST_FRAMEWORK = {
    # Default schema class change karo — drf-spectacular wala
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'My API',
    'DESCRIPTION': 'Production API documentation — sab endpoints yahan milenge',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,   # /api/schema/ ko docs mein mat dikhao
    'COMPONENT_SPLIT_REQUEST': True,  # Request/Response alag-alag dikhao
    
    # JWT Authentication button Swagger mein
    'SECURITY': [{"BearerAuth": []}],
    'COMPONENTS': {
        'securitySchemes': {
            'BearerAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
        }
    }
}


# ===== urls.py =====
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    # Schema download karo (YAML/JSON)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    
    # Swagger UI — interactive browser
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # ReDoc — cleaner documentation view
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
```

---

### @extend_schema — Customization Decorator

```python
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

class ProductViewSet(ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    
    @extend_schema(
        summary="List all products",
        description="Returns paginated list of products with optional filters. "
                    "Default page size 20. Max 100.",
        parameters=[
            OpenApiParameter(
                name='category',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,   # Query param ?category=electronics
                description='Filter by category (electronics, clothing, books)',
                required=False,
                examples=[
                    OpenApiExample('Electronics', value='electronics'),
                    OpenApiExample('Clothing', value='clothing'),
                ]
            ),
            OpenApiParameter(
                name='min_price',
                type=OpenApiTypes.FLOAT,
                location=OpenApiParameter.QUERY,
                description='Minimum price filter — e.g. ?min_price=1000'
            ),
            OpenApiParameter(
                name='max_price',
                type=OpenApiTypes.FLOAT,
                location=OpenApiParameter.QUERY,
                description='Maximum price filter'
            ),
        ],
        responses={
            200: ProductSerializer(many=True),
            401: OpenApiTypes.OBJECT,   # Unauthorized
        },
        tags=['Products']   # Swagger mein grouping
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Create product",
        description="Create a new product. Admin only.",
        request=ProductSerializer,
        responses={
            201: ProductSerializer,
            400: OpenApiTypes.OBJECT,   # Validation error
            403: OpenApiTypes.OBJECT,   # Permission denied
        },
        examples=[
            OpenApiExample(
                'Valid Product Example',
                value={
                    'name': 'Laptop Pro',
                    'price': '75000.00',
                    'category': 'electronics'
                },
                request_only=True,   # Sirf request mein dikhao, response mein nahi
            )
        ],
        tags=['Products']
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)
    
    @extend_schema(
        summary="Get product by ID",
        responses={
            200: ProductSerializer,
            404: OpenApiTypes.OBJECT,
        },
        tags=['Products']
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
    
    @extend_schema(
        summary="Delete product",
        responses={
            204: None,   # No content
            404: OpenApiTypes.OBJECT,
        },
        tags=['Products']
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
```

---

### Custom Response Schemas — Inline Serializer

```python
from drf_spectacular.utils import inline_serializer
import rest_framework.serializers as s

# Jab response ka koi dedicated serializer na ho — inline banao
@extend_schema(
    summary="User Login",
    description="Email/password se login karo, JWT tokens milenge.",
    request=inline_serializer(
        name='LoginRequest',
        fields={
            'email': s.EmailField(),
            'password': s.CharField(),
        }
    ),
    responses={
        200: inline_serializer(
            name='LoginResponse',
            fields={
                'access': s.CharField(help_text="JWT access token (15 min valid)"),
                'refresh': s.CharField(help_text="JWT refresh token (7 days valid)"),
                'user': UserSerializer(),
            }
        ),
        400: inline_serializer(
            name='LoginError',
            fields={
                'detail': s.CharField(help_text="Error message"),
            }
        )
    },
    tags=['Authentication']
)
@api_view(['POST'])
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    # ... authentication logic
    return Response({'access': access_token, 'refresh': refresh_token, 'user': user_data})
```

---

### Schema Generation Commands

```bash
# Schema YAML file generate karo (CI/CD mein useful)
python manage.py spectacular --color --file schema.yml

# JSON format mein
python manage.py spectacular --color --format json --file schema.json

# Validation — koi errors hain?
python manage.py spectacular --validate

# Specific URL ke liye
python manage.py spectacular --url-conf myapp.urls --file schema.yml
```

---

### Excluding Endpoints from Docs

```python
# Koi endpoint Swagger mein nahi dikhana
@extend_schema(exclude=True)
@api_view(['GET'])
def internal_health_check(request):
    return Response({'status': 'ok'})

# Pura ViewSet exclude karo
@extend_schema(exclude=True)
class InternalAdminViewSet(ModelViewSet):
    ...
```

---

### Interview Questions — API Documentation

**Q1. drf-spectacular vs drf-yasg — kya fark hai? Kaunsa use karein?**

**A:**
```
drf-yasg (Older):
  - OpenAPI 2.0 (Swagger 2.0) generate karta hai
  - Active maintenance slow ho gaya hai
  - DRF ke newer features ke saath issues aate hain
  - Custom schema likhna complex tha

drf-spectacular (Modern, Recommended):
  - OpenAPI 3.0 generate karta hai (latest standard)
  - DRF ke saath deeply integrated — ViewSets, serializers auto-detect
  - @extend_schema decorator — clean, Python-first customization
  - Inline serializers, custom examples, request/response split
  - Active maintenance, DRF team recommend karta hai

Production mein drf-spectacular hi use karo.
OpenAPI 3.0 = better security schemes, better type system, better tooling.
```

---

**Q2. @extend_schema decorator kahan aur kyun use karte hain?**

**A:**
```
drf-spectacular ViewSets se automatically schema generate karta hai,
lekin kuch cheezein manually batani padhti hain:

1. Query Parameters document karo:
   @extend_schema(parameters=[OpenApiParameter('search', OpenApiTypes.STR)])
   → ?search=laptop Swagger mein dikhega test field ke saath

2. Response codes specify karo:
   @extend_schema(responses={200: ProductSerializer, 404: OpenApiTypes.OBJECT})
   → Docs mein clearly dikhega kab kya milega

3. Examples add karo:
   → Frontend developers ko exact format pata chale

4. Tags se group karo:
   → /api/docs/ mein "Products", "Auth", "Orders" sections ban jayenge

5. Summary/Description:
   → Non-technical stakeholders bhi samjhein

@extend_schema kab nahi chahiye:
  - Simple CRUD jahan serializer khud sab document karta hai
  - Internal-only endpoints (use exclude=True)
```

---

**Q3. JWT authentication Swagger UI mein kaise add karein?**

**A:**
```python
# SPECTACULAR_SETTINGS mein ye add karo:
SPECTACULAR_SETTINGS = {
    'TITLE': 'My API',
    'VERSION': '1.0.0',
    
    # Step 1: Global security requirement
    'SECURITY': [{"BearerAuth": []}],
    
    # Step 2: Security scheme define karo
    'COMPONENTS': {
        'securitySchemes': {
            'BearerAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
        }
    }
}

# Ab Swagger UI mein "Authorize" button aayega.
# User: Bearer <token> enter karega.
# Sab requests mein automatically Authorization header jayega.

# Specific endpoint pe override karna ho:
@extend_schema(security=[])  # Is endpoint pe auth ki zaroorat nahi
@api_view(['GET'])
def public_endpoint(request):
    ...
```

---

**Q4. API versioning ke saath documentation kaise manage karein?**

**A:**
```python
# URL-based versioning ke saath:
# v1/products/ aur v2/products/ alag docs chahiye

# settings.py
SPECTACULAR_SETTINGS = {
    'TITLE': 'My API',
    'VERSION': '2.0.0',
}

# urls.py — alag schema endpoints
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # V1 docs
    path('api/v1/schema/', SpectacularAPIView.as_view(
        urlconf='myapp.urls_v1'
    ), name='schema-v1'),
    path('api/v1/docs/', SpectacularSwaggerView.as_view(url_name='schema-v1')),
    
    # V2 docs
    path('api/v2/schema/', SpectacularAPIView.as_view(
        urlconf='myapp.urls_v2'
    ), name='schema-v2'),
    path('api/v2/docs/', SpectacularSwaggerView.as_view(url_name='schema-v2')),
]

# Versioning strategy:
#   - v1 maintain karo backward compatibility ke liye
#   - v2 naye features ke saath
#   - Deprecation notice v1 description mein add karo
```

---

**Q5. Production mein API docs secure kaise karein?**

**A:**
```python
# Option 1: Staff-only access
from drf_spectacular.views import SpectacularSwaggerView
from rest_framework.permissions import IsAdminUser

class SecureSwaggerView(SpectacularSwaggerView):
    permission_classes = [IsAdminUser]

urlpatterns = [
    path('api/docs/', SecureSwaggerView.as_view(url_name='schema')),
]

# Option 2: Sirf DEBUG=True pe available
from django.conf import settings

if settings.DEBUG:
    urlpatterns += [
        path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema')),
    ]

# Option 3: IP whitelist (nginx level better hai)
class IPRestrictedSwaggerView(SpectacularSwaggerView):
    allowed_ips = ['10.0.0.0/8', '192.168.1.100']
    
    def dispatch(self, request, *args, **kwargs):
        ip = request.META.get('REMOTE_ADDR')
        if ip not in self.allowed_ips:
            return HttpResponse('Forbidden', status=403)
        return super().dispatch(request, *args, **kwargs)

# Best practice:
#   Development: Open access, full docs
#   Staging: Auth required (IsAdminUser)
#   Production: VPN/IP restriction + Auth
```

---

## Summary Table

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    TOPIC SUMMARY                                           │
├─────────────────────┬──────────────────────────────────────────────────────┤
│ TOPIC               │ KEY CONCEPTS                                         │
├─────────────────────┼──────────────────────────────────────────────────────┤
│ Multi-Tenancy       │ SaaS pattern — ek app, multiple companies            │
│ Approach 1          │ tenant_id column + Custom Manager + Middleware        │
│ Approach 2          │ django-tenants + PostgreSQL schemas (recommended)    │
│ Approach 3          │ DB per tenant + Database Router (enterprise)         │
│ Middleware role      │ Subdomain → Tenant identify → request.tenant set    │
│ Data safety         │ Manager filter + ViewSet mixin + tests               │
├─────────────────────┼──────────────────────────────────────────────────────┤
│ drf-spectacular     │ OpenAPI 3.0 auto-generation for DRF                  │
│ Setup               │ DEFAULT_SCHEMA_CLASS + SPECTACULAR_SETTINGS          │
│ @extend_schema      │ Summary, parameters, responses, examples, tags       │
│ inline_serializer   │ One-off response schemas without creating new class  │
│ Auth in Swagger     │ SECURITY + securitySchemes in SPECTACULAR_SETTINGS   │
│ Commands            │ manage.py spectacular --file schema.yml              │
│ Production          │ IsAdminUser permission on docs views                 │
└─────────────────────┴──────────────────────────────────────────────────────┘
```

---

*Next: 11_deployment_performance.md — Gunicorn, Nginx, Redis, Celery production setup*
