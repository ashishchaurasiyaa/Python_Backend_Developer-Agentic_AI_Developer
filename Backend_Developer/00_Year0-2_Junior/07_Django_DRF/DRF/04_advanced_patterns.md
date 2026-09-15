# DRF — Advanced Patterns

## Topics
- django-filter + SearchFilter + OrderingFilter
- Dynamic Fields Serializer
- DRF Nested Serializer Write (create/update)
- DRF Throttling

> Django-side advanced patterns (Custom User Model, transactions, caching, admin customization) moved to [`../Django/04_advanced_patterns.md`](../Django/04_advanced_patterns.md).

---

## Interview Questions & Answers

### Q1: django-filter vs SearchFilter vs OrderingFilter — kab kya use karte hain?

**Answer:**
```python
# settings.py
REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",  # ?status=published
        "rest_framework.filters.SearchFilter",                 # ?search=django
        "rest_framework.filters.OrderingFilter",               # ?ordering=-created_at
    ]
}

class PostViewSet(viewsets.ModelViewSet):
    # django-filter — exact/range filtering
    filterset_class = PostFilter  # custom FilterSet class

    # OR simple filterset_fields (no custom FilterSet needed):
    # filterset_fields = {"status": ["exact"], "author": ["exact"]}

    # SearchFilter — text search across these fields
    search_fields = ["title", "content", "^author__email"]  # ^ = startswith
    # ^ = startswith, = = exact, @ = full-text search (PostgreSQL), $ = regex

    # OrderingFilter — only these fields can be sorted
    ordering_fields = ["created_at", "views_count", "title"]
    ordering = ["-created_at"]  # default ordering

# Usage:
# GET /posts/?status=published                  → DjangoFilterBackend
# GET /posts/?search=django+tutorial            → SearchFilter
# GET /posts/?ordering=-views_count,title       → OrderingFilter
# GET /posts/?status=published&search=orm&ordering=-created_at  → all combined
```

---

### Q2: Nested Serializer Write kaise karte hain?

**Answer:**
```python
class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ["street", "city", "country", "postal_code"]

class UserSerializer(serializers.ModelSerializer):
    # Read: nested dict
    # Write: nested dict → create/update Address
    address = AddressSerializer(required=False)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "address"]

    def create(self, validated_data):
        # Pop nested data before creating parent
        address_data = validated_data.pop("address", None)
        user = User.objects.create(**validated_data)

        if address_data:
            Address.objects.create(user=user, **address_data)

        return user

    def update(self, instance, validated_data):
        address_data = validated_data.pop("address", None)

        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update or create address
        if address_data:
            Address.objects.update_or_create(
                user=instance,
                defaults=address_data
            )
        return instance
```

---

### Q3: DRF Serializer `to_representation` ka use case?

**Answer:**
```python
class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ["id", "title", "content", "author", "created_at"]

    def to_representation(self, instance):
        """
        Override how the serialized output looks.
        Use cases:
          - Add computed fields not in model
          - Transform field values (datetime → human-readable)
          - Conditional fields based on user role
          - Remove sensitive fields for non-admin
        """
        data = super().to_representation(instance)

        # Add computed field
        data["reading_time"] = f"{instance.read_time_minutes} min read"

        # Conditional field — show content preview in list, full in detail
        request = self.context.get("request")
        if request and request.method == "GET" and "pk" not in request.resolver_match.kwargs:
            # List view — truncate content
            data["content"] = data["content"][:200] + "..."

        # Remove fields based on role
        if request and not request.user.is_staff:
            data.pop("internal_notes", None)

        return data
```

---

### Q4: DRF Throttling — custom throttle kaise banate hain?

**Answer:**
```python
from rest_framework.throttling import SimpleRateThrottle

class PerUserPerEndpointThrottle(SimpleRateThrottle):
    """Per-user throttle with custom scope from view."""
    scope = "user"

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None  # fallback to anon throttle
        return f"throttle_{self.scope}_{request.user.id}_{view.__class__.__name__}"

class AIGenerationThrottle(SimpleRateThrottle):
    """Strict throttle for expensive AI operations."""
    scope = "ai_generation"
    rate  = "10/hour"

    def get_rate(self):
        # Dynamic rate based on user plan
        from rest_framework.throttling import SimpleRateThrottle
        if hasattr(self, "request"):
            plan = getattr(self.request.user, "plan", "free")
            return {"free": "5/hour", "premium": "100/hour"}.get(plan, "5/hour")
        return self.rate

# settings.py
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_RATES": {
        "ai_generation": "10/hour",
        "login":         "5/minute",
    }
}
```
