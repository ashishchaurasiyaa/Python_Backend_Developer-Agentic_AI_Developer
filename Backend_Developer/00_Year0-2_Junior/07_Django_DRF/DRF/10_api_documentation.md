# API Documentation with drf-spectacular

## DRF — Interview Prep (Hinglish Style)

> Multi-tenant architecture (Django-level) moved to [`../Django/10_multitenant_architecture.md`](../Django/10_multitenant_architecture.md).

---

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
│ drf-spectacular     │ OpenAPI 3.0 auto-generation for DRF                  │
│ Setup               │ DEFAULT_SCHEMA_CLASS + SPECTACULAR_SETTINGS          │
│ @extend_schema      │ Summary, parameters, responses, examples, tags       │
│ inline_serializer   │ One-off response schemas without creating new class  │
│ Auth in Swagger     │ SECURITY + securitySchemes in SPECTACULAR_SETTINGS   │
│ Commands            │ manage.py spectacular --file schema.yml              │
│ Production          │ IsAdminUser permission on docs views                 │
└─────────────────────┴──────────────────────────────────────────────────────┘
```
