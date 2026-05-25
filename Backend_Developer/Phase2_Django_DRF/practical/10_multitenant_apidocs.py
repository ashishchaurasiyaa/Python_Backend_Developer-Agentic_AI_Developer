"""
Multi-Tenant Architecture & API Documentation — Practical Implementation
========================================================================
Hinglish comments ke saath complete working code.

Sections:
  1. TenantMiddleware — Full implementation (subdomain + JWT + header)
  2. Shared Schema Models — TenantManager, TenantAwareModel, Tenant, Product
  3. drf-spectacular — Full ViewSet with @extend_schema decorators
  4. Tenant-aware DRF ViewSet — TenantFilterMixin + ProductViewSet

NOTE: Ye file Django project ke andar run nahi hogi seedha.
      Concepts aur patterns samjhne ke liye hai.
      Asli project mein proper app structure mein daalo.
"""

# =============================================================================
# IMPORTS (production project mein ye split hogi alag-alag files mein)
# =============================================================================
import threading
from typing import Optional

# Django imports
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.utils.functional import SimpleLazyObject

# DRF imports
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

# drf-spectacular imports
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    extend_schema,
    inline_serializer,
)
from drf_spectacular.types import OpenApiTypes


# =============================================================================
# SECTION 1: TENANT MIDDLEWARE — Complete Implementation
# =============================================================================
# Yahan teen methods hain tenant identify karne ke:
#   Method A: Subdomain se    → company1.myapp.com
#   Method B: JWT token se    → payload mein tenant_id
#   Method C: Custom header   → X-Tenant-ID: company1
#
# Production mein aksar Method A preferred hai — clean, intuitive.
# Internal APIs ke liye Method C bhi common hai.
# =============================================================================

class TenantMiddleware:
    """
    Multi-strategy Tenant Middleware.

    Priority order:
      1. Subdomain (company1.myapp.com) ← Primary strategy
      2. X-Tenant-ID header             ← API clients ke liye fallback
      3. JWT token payload              ← Mobile apps ke liye

    Koi bhi strategy kaam kare → request.tenant set ho jayega.
    Koi bhi nahi chali → 404 return karo.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = self._identify_tenant(request)

        if tenant is None:
            # Tenant identify nahi hua — request reject karo
            return JsonResponse(
                {"error": "Tenant not found or inactive"},
                status=404
            )

        # Request pe tenant lagao — views mein request.tenant milega
        request.tenant = tenant

        # Thread-local mein bhi set karo — Custom Manager use karega
        set_current_tenant(tenant)

        response = self.get_response(request)

        # Request khatam — thread-local clean karo (memory leak prevent)
        set_current_tenant(None)

        return response

    def _identify_tenant(self, request) -> Optional["Tenant"]:
        """
        Teen strategies try karo, pehli successful wali return karo.
        """
        # --- Strategy 1: Subdomain ---
        # company1.myapp.com → subdomain = "company1"
        tenant = self._from_subdomain(request)
        if tenant:
            return tenant

        # --- Strategy 2: Custom Header ---
        # X-Tenant-ID: company1  (API clients/Postman ke liye useful)
        tenant = self._from_header(request)
        if tenant:
            return tenant

        # --- Strategy 3: JWT Token ---
        # JWT payload mein tenant_id field se
        tenant = self._from_jwt(request)
        if tenant:
            return tenant

        return None

    def _from_subdomain(self, request) -> Optional["Tenant"]:
        """
        company1.myapp.com → "company1" subdomain nikalo.

        Edge cases handle:
          - localhost (development) → None return karo, skip
          - www.myapp.com → "www" wala tenant nahi hoga, None
          - IP address → None
        """
        host = request.get_host().split(':')[0]   # Port remove karo

        # localhost pe development → subdomain strategy skip karo
        if host in ('localhost', '127.0.0.1') or host.replace('.', '').isdigit():
            return None

        parts = host.split('.')
        if len(parts) < 3:
            # "myapp.com" → koi subdomain nahi
            return None

        subdomain = parts[0]   # "company1"

        # "www" subdomain tenant nahi hai
        if subdomain == 'www':
            return None

        try:
            return Tenant.objects.get(subdomain=subdomain, is_active=True)
        except Tenant.DoesNotExist:
            return None

    def _from_header(self, request) -> Optional["Tenant"]:
        """
        HTTP Header: X-Tenant-ID: company1
        Postman/API clients ke liye convenient.
        """
        tenant_id = request.META.get('HTTP_X_TENANT_ID')
        if not tenant_id:
            return None

        try:
            return Tenant.objects.get(subdomain=tenant_id, is_active=True)
        except Tenant.DoesNotExist:
            return None

    def _from_jwt(self, request) -> Optional["Tenant"]:
        """
        JWT token ke payload mein tenant_id field se.

        Token payload example:
        {
            "user_id": 42,
            "tenant_id": "company1",   ← Ye nikalo
            "exp": 1735000000
        }

        Ye tab useful hai jab:
          - Mobile app use kar raha hai
          - Subdomain nahi use kar rahe
          - Single domain pe multiple tenants serve karna hai
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ')[1]

        try:
            import jwt as pyjwt
            from django.conf import settings

            # Token decode karo (verification ke bina sirf read)
            # Real app mein verification zaroori hai
            payload = pyjwt.decode(
                token,
                options={"verify_signature": False}
            )
            tenant_id = payload.get('tenant_id')

            if not tenant_id:
                return None

            return Tenant.objects.get(subdomain=tenant_id, is_active=True)

        except Exception:
            # JWT decode fail hua — ye strategy kaam nahi ki, next try
            return None


# =============================================================================
# SECTION 2: SHARED SCHEMA MODELS — Thread-local + Custom Manager
# =============================================================================
# Approach: Shared DB, Shared Schema
#   - Sab tenants ke data ek hi tables mein
#   - tenant_id column har jagah
#   - TenantManager → automatically filter karta hai
#   - Thread-local → current request ka tenant store karta hai
#
# Pros: Simple, any DB works, cheap
# Cons: Galti se data leak ho sakta hai, large tables
# =============================================================================

# Thread-local storage — har thread (request) ka apna current_tenant
_thread_locals = threading.local()


def get_current_tenant() -> Optional["Tenant"]:
    """
    Thread-local se current request ka tenant nikalo.
    Middleware ne set kiya hoga.
    None milega agar:
      - Admin context mein ho
      - Middleware ne set nahi kiya
      - Background task chal rahi ho
    """
    return getattr(_thread_locals, 'current_tenant', None)


def set_current_tenant(tenant: Optional["Tenant"]) -> None:
    """
    Thread-local mein current tenant set karo.
    Middleware use karta hai request start pe.
    Request khatam hone pe None set karo (cleanup).
    """
    _thread_locals.current_tenant = tenant


class TenantManager(models.Manager):
    """
    Custom Manager — Har query automatically current tenant ke liye filter hogi.

    Kaise kaam karta hai:
      Product.objects.all()
      → Internally: Product.objects.filter(tenant=current_tenant)
      → Company A ka user Company B ka data nahi dekh sakta

    Override kiya hai: get_queryset() — sab queries yahan se guzarti hain.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = get_current_tenant()

        if tenant is not None:
            # Current tenant ke liye filter — yahi magic hai
            return qs.filter(tenant=tenant)

        # Koi tenant set nahi (admin panel, management commands, tests)
        # Sab data return karo — caller ko pata hai kya kar raha hai
        return qs


class TenantAwareModel(models.Model):
    """
    Abstract base class — sab tenant-specific models isse inherit karein.

    Do managers:
      objects      → Tenant-filtered (default, views mein use karo)
      all_objects  → Unfiltered (admin panel, cross-tenant operations)

    related_name='%(class)ss':
      Product → tenant.products.all()
      Order   → tenant.orders.all()
      (Automatically class name se related name ban jata hai)
    """

    tenant = models.ForeignKey(
        'Tenant',
        on_delete=models.CASCADE,
        related_name='%(class)ss',   # Dynamic related_name — conflict nahi hoga
        db_index=True,               # Har query mein tenant filter → index zaroori
    )

    objects = TenantManager()           # Default: tenant-filtered queries
    all_objects = models.Manager()      # Escape hatch: unfiltered (admin use)

    class Meta:
        abstract = True   # Koi table nahi banegi is model ki


class Tenant(models.Model):
    """
    Tenant = ek company ya organization.

    subdomain → URL routing ke liye (company1.myapp.com)
    plan      → Billing/feature gating ke liye
    is_active → Disabled tenants ko access nahi milega
    """

    PLAN_CHOICES = [
        ('free', 'Free'),
        ('pro', 'Pro'),
        ('enterprise', 'Enterprise'),
    ]

    name = models.CharField(max_length=100)
    subdomain = models.SlugField(unique=True)   # URL-safe, unique
    is_active = models.BooleanField(default=True)
    plan = models.CharField(choices=PLAN_CHOICES, max_length=20, default='free')
    created_at = models.DateTimeField(auto_now_add=True)

    # Optional: Tenant ka admin user
    admin_email = models.EmailField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.subdomain})"

    @property
    def base_url(self):
        """Tenant ka main URL nikalo."""
        return f"https://{self.subdomain}.myapp.com"


class Product(TenantAwareModel):
    """
    Product model — TenantAwareModel se inherit kiya.

    unique_together → Ek tenant ke andar product name unique hoga.
    Company A aur Company B dono "Laptop" rakh sakte hain → allowed.
    Company A mein do "Laptop" → not allowed.
    """

    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=100, blank=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Tenant ke andar unique name enforce karo
        unique_together = ['tenant', 'name']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} (Tenant: {self.tenant.name})"


class Order(TenantAwareModel):
    """
    Order model — ek aur example of TenantAwareModel.
    Product bhi tenant-aware hai, toh yahan ForeignKey safe hai.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    # Product bhi is tenant ka hoga — cross-tenant order possible nahi
    # (Validation ViewSet ya Serializer mein add karo)
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,    # Order hai toh product delete mat karo
        related_name='orders',
    )
    quantity = models.PositiveIntegerField()
    status = models.CharField(choices=STATUS_CHOICES, max_length=20, default='pending')
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.pk} - {self.product.name}"


# =============================================================================
# SECTION 3: drf-spectacular — Complete ViewSet with Documentation
# =============================================================================
# Har endpoint ke liye:
#   - Summary (ek line)
#   - Description (detail mein)
#   - Parameters (query params, path params)
#   - Request/Response schemas
#   - Examples (frontend devs ke liye)
#   - Tags (grouping ke liye)
# =============================================================================

class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer — drf-spectacular isse automatically schema mein use karega.
    help_text → Swagger mein description aayegi.
    """

    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'category', 'is_available', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0.")
        return value


class ProductDetailSerializer(ProductSerializer):
    """
    Create/Update ke liye alag serializer — tenant field nahi (auto-set hoga).
    """
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)

    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + ['tenant_name', 'updated_at']


@extend_schema(tags=['Products'])   # Class-level tag — sab methods pe apply hoga
class DocumentedProductViewSet(ModelViewSet):
    """
    Product CRUD ViewSet — full drf-spectacular documentation ke saath.

    Har action pe @extend_schema lagaya hai:
      - list: query params, 200/401 responses
      - create: request body, 201/400/403 responses
      - retrieve: path param, 200/404
      - update: request + response, 200/400/404
      - destroy: 204/404
    """

    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        # Detail aur list ke liye alag serializers
        if self.action in ('retrieve', 'update', 'partial_update'):
            return ProductDetailSerializer
        return ProductSerializer

    @extend_schema(
        summary="List all products",
        description=(
            "Returns paginated list of products for the current tenant. "
            "Optional filters: category, price range, availability. "
            "Default page size: 20. Maximum: 100."
        ),
        parameters=[
            OpenApiParameter(
                name='category',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Filter by category (electronics, clothing, books)',
                examples=[
                    OpenApiExample('Electronics filter', value='electronics'),
                    OpenApiExample('Clothing filter', value='clothing'),
                ],
            ),
            OpenApiParameter(
                name='min_price',
                type=OpenApiTypes.FLOAT,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Minimum price — e.g. ?min_price=1000.00',
            ),
            OpenApiParameter(
                name='max_price',
                type=OpenApiTypes.FLOAT,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Maximum price — e.g. ?max_price=50000.00',
            ),
            OpenApiParameter(
                name='is_available',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Sirf available products: ?is_available=true',
            ),
        ],
        responses={
            200: ProductSerializer(many=True),
            401: inline_serializer(
                name='UnauthorizedError',
                fields={'detail': serializers.CharField()}
            ),
        },
    )
    def list(self, request, *args, **kwargs):
        """
        Query params ke saath filter apply karo, phir parent list() call karo.
        """
        queryset = self.get_queryset()

        # Query params se dynamic filtering
        category = request.query_params.get('category')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        is_available = request.query_params.get('is_available')

        if category:
            queryset = queryset.filter(category__iexact=category)
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        if is_available is not None:
            queryset = queryset.filter(is_available=is_available.lower() == 'true')

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create a new product",
        description="New product create karo current tenant ke liye. Tenant auto-assign hoga.",
        request=ProductSerializer,
        responses={
            201: ProductSerializer,
            400: inline_serializer(
                name='ValidationError',
                fields={
                    'field_name': serializers.ListField(child=serializers.CharField()),
                }
            ),
            403: inline_serializer(
                name='PermissionDenied',
                fields={'detail': serializers.CharField()}
            ),
        },
        examples=[
            OpenApiExample(
                'Electronics Product',
                value={
                    'name': 'Laptop Pro 2024',
                    'price': '75000.00',
                    'category': 'electronics',
                    'is_available': True,
                },
                request_only=True,   # Sirf request example mein dikhao
            ),
            OpenApiExample(
                'Clothing Product',
                value={
                    'name': 'Cotton T-Shirt',
                    'price': '499.00',
                    'category': 'clothing',
                    'is_available': True,
                },
                request_only=True,
            ),
        ],
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        summary="Get product by ID",
        description="Single product ki full details — tenant ke liye.",
        responses={
            200: ProductDetailSerializer,
            404: inline_serializer(
                name='ProductNotFound',
                fields={'detail': serializers.CharField()}
            ),
        },
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Update product (full)",
        description="Product ko fully update karo. Sab required fields bhejne padenge.",
        request=ProductSerializer,
        responses={
            200: ProductDetailSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Update product (partial)",
        description="Sirf changed fields bhejo — PATCH request. Baaki fields waise rahenge.",
        request=ProductSerializer,
        responses={
            200: ProductDetailSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(
        summary="Delete product",
        description="Product delete karo. Permanent action — undo nahi hoga.",
        responses={
            204: None,   # No content — delete successful
            404: inline_serializer(
                name='DeleteNotFound',
                fields={'detail': serializers.CharField()}
            ),
        },
    )
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


# Login endpoint — inline_serializer use karo (dedicated serializer nahi chahiye)
@extend_schema(
    summary="User Login",
    description=(
        "Email aur password se login karo. "
        "Success pe JWT access + refresh tokens milenge. "
        "Access token 15 minutes valid, Refresh token 7 days."
    ),
    request=inline_serializer(
        name='LoginRequest',
        fields={
            'email': serializers.EmailField(help_text="Registered email address"),
            'password': serializers.CharField(
                help_text="Account password",
                style={'input_type': 'password'}  # Swagger mein hidden input
            ),
        }
    ),
    responses={
        200: inline_serializer(
            name='LoginResponse',
            fields={
                'access': serializers.CharField(help_text="JWT access token (15 min)"),
                'refresh': serializers.CharField(help_text="JWT refresh token (7 days)"),
                'user_id': serializers.IntegerField(),
                'email': serializers.EmailField(),
                'tenant': serializers.CharField(help_text="Current tenant subdomain"),
            }
        ),
        400: inline_serializer(
            name='LoginError',
            fields={'detail': serializers.CharField(help_text="Error description")}
        ),
        401: inline_serializer(
            name='LoginUnauthorized',
            fields={'detail': serializers.CharField(help_text="Invalid credentials")}
        ),
    },
    tags=['Authentication'],
)
@api_view(['POST'])
def login_view(request):
    """
    Login endpoint — JWT tokens return karta hai.
    drf-spectacular inline_serializer use kiya hai
    kyunki ye simple endpoint hai, dedicated serializer overkill hoga.
    """
    email = request.data.get('email')
    password = request.data.get('password')

    # Actual authentication logic yahan hogi...
    # Example ke liye placeholder:
    return Response({
        'access': 'eyJ...',
        'refresh': 'eyJ...',
        'user_id': 1,
        'email': email,
        'tenant': request.tenant.subdomain if hasattr(request, 'tenant') else None,
    })


# =============================================================================
# SECTION 4: TENANT-AWARE DRF VIEWSET — TenantFilterMixin
# =============================================================================
# TenantFilterMixin → Reusable mixin jo automatically:
#   1. get_queryset() mein tenant filter lagate hain
#   2. perform_create() mein tenant assign karte hain
#   3. Cross-tenant object access ko block karte hain
#
# Pattern: Mixin pehle, ModelViewSet baad mein
#   class ProductViewSet(TenantFilterMixin, ModelViewSet)
#                         ↑ Pehle              ↑ Baad mein
#   MRO (Method Resolution Order) sahi kaam karega
# =============================================================================

class TenantFilterMixin:
    """
    Reusable Mixin — Kisi bhi ViewSet mein tenant filtering add karo.

    Usage:
        class ProductViewSet(TenantFilterMixin, ModelViewSet):
            queryset = Product.objects.all()

    Automatically:
        - Sirf current tenant ke records dikhayega
        - Naye records mein current tenant assign karega
        - Cross-tenant URL manipulation block karega (get_object override)
    """

    def get_queryset(self):
        """
        request.tenant middleware ne set kiya hai.
        Sirf is tenant ke records return karo.

        Agar kisi reason se tenant nahi milta →
        empty queryset return karo (leak nahi hoga kabhi bhi).
        """
        tenant = getattr(self.request, 'tenant', None)

        if tenant is None:
            # Safety net — tenant missing → kuch bhi mat dikhao
            return super().get_queryset().none()

        return super().get_queryset().filter(tenant=tenant)

    def perform_create(self, serializer):
        """
        Create pe automatically current tenant assign karo.
        User ko tenant field POST nahi karna padega (security bhi achha).
        """
        tenant = getattr(self.request, 'tenant', None)

        if tenant is None:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Tenant context missing. Cannot create.")

        # tenant field force-set karo — user provided value override hogi
        serializer.save(tenant=tenant)

    def get_object(self):
        """
        URL manipulation se cross-tenant access block karo.

        Attack scenario:
          Company A ka user /api/products/999/ try karta hai
          jahan 999 Company B ka product ID hai.

        get_queryset() pehle se tenant-filtered hai,
        toh get_object() automatically 404 return karega.
        Extra check nahi chahiye — but clear karte hain yahan.
        """
        # get_queryset() already tenant-filtered hai
        # Super call karega → 404 if not in queryset
        obj = super().get_object()

        # Double-check (defense in depth) — explicit validation
        tenant = getattr(self.request, 'tenant', None)
        if tenant and hasattr(obj, 'tenant') and obj.tenant != tenant:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You don't have access to this resource.")

        return obj


class ProductTenantViewSet(TenantFilterMixin, DocumentedProductViewSet):
    """
    Final Production-ready ViewSet:
      - TenantFilterMixin → Tenant isolation
      - DocumentedProductViewSet → drf-spectacular docs
      - ModelViewSet → CRUD operations

    Ye ViewSet:
      1. Request se tenant read karta hai (middleware ne set kiya)
      2. Sirf us tenant ke products dikhata hai
      3. New products mein tenant auto-set karta hai
      4. Cross-tenant access block karta hai
      5. Swagger mein fully documented hai
    """

    # queryset aur serializer_class parent se inherit ho rahe hain
    # Koi extra code nahi chahiye — sab mixins kaam kar rahe hain

    def get_queryset(self):
        """
        Chain: TenantFilterMixin → DocumentedProductViewSet → ModelViewSet

        TenantFilterMixin.get_queryset():
          return super().filter(tenant=request.tenant)
             ↓
        ModelViewSet.get_queryset():
          return Product.objects.all()

        Final result: Product.objects.filter(tenant=request.tenant)
        """
        return super().get_queryset()


# =============================================================================
# BONUS: Tenant Onboarding Helper
# =============================================================================
# New company sign up karti hai → ye function call karo
# Schema per Tenant approach ke liye (django-tenants library)
# =============================================================================

def onboard_new_tenant_shared_schema(
    company_name: str,
    subdomain: str,
    plan: str = 'free',
    admin_email: str = '',
) -> "Tenant":
    """
    Shared Schema approach mein new tenant onboard karo.

    Steps:
      1. Validate subdomain available hai
      2. Tenant record create karo
      3. Default seed data create karo (optional)
      4. Welcome email queue karo

    Args:
        company_name: "Acme Corp"
        subdomain:    "acme" → acme.myapp.com
        plan:         "free", "pro", "enterprise"
        admin_email:  Admin ko email bhejne ke liye

    Returns:
        Naya Tenant object

    Raises:
        ValueError: Agar subdomain already taken ho
    """
    from django.db import transaction

    # Subdomain reserved words check karo
    reserved = {'www', 'api', 'admin', 'mail', 'ftp', 'app', 'cdn', 'static'}
    if subdomain.lower() in reserved:
        raise ValueError(f"'{subdomain}' is a reserved subdomain.")

    # Already exists check
    if Tenant.objects.filter(subdomain=subdomain).exists():
        raise ValueError(f"Subdomain '{subdomain}' is already taken.")

    with transaction.atomic():
        tenant = Tenant.objects.create(
            name=company_name,
            subdomain=subdomain,
            plan=plan,
            admin_email=admin_email,
            is_active=True,
        )

        # Default data seed karo (optional — business logic pe depend karta hai)
        _seed_default_data(tenant)

    # Email queue karo (Celery task)
    # send_welcome_email.delay(admin_email, subdomain)   ← Uncomment if Celery hai

    return tenant


def _seed_default_data(tenant: "Tenant") -> None:
    """
    New tenant ke liye default/sample data create karo.
    Ye optional hai — agar onboarding experience better banana ho.
    """
    # Example: Default categories ya settings create karo
    # Yahan koi bhi tenant-specific initial data create kar sakte ho
    pass


# =============================================================================
# DEMO: How to use in tests
# =============================================================================
# Ye pytest/Django test case mein kaise use karein:
#
# def test_tenant_isolation():
#     """Company A ka product Company B ko nahi dikhna chahiye."""
#     company_a = Tenant.objects.create(name="Company A", subdomain="company-a")
#     company_b = Tenant.objects.create(name="Company B", subdomain="company-b")
#
#     # Company A ka product banao
#     set_current_tenant(company_a)
#     product_a = Product.all_objects.create(
#         tenant=company_a, name="Laptop", price=50000
#     )
#
#     # Company A context mein — apna product dikhna chahiye
#     assert Product.objects.count() == 1
#     assert Product.objects.first().name == "Laptop"
#
#     # Company B context mein switch karo
#     set_current_tenant(company_b)
#     assert Product.objects.count() == 0   # Company B ka koi product nahi
#
#     # Cleanup
#     set_current_tenant(None)
#
# =============================================================================
