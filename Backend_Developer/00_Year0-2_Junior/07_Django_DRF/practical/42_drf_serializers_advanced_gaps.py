"""
DRF Serializers Advanced Gaps
==============================
Covers the five categories that trip up candidates in Round-2 interviews:

  1. Writable nested serializers — WHY DRF refuses to do it automatically, and
     how to implement both create() and the two canonical update() strategies
     (replace-all vs match-by-id).
  2. Validators & validation ORDER — UniqueValidator, UniqueTogetherValidator,
     and the exact field → object pipeline that runs inside is_valid().
  3. Serializer context — what GenericAPIView injects by default, how to add
     custom keys, and the common traps when context is absent.
  4. Logic placement — perform_create vs serializer.create() vs service layer.
  5. SerializerMethodField N+1, ListSerializer internals, bulk create, and
     the DynamicFieldsModelSerializer recipe.

This module is written as importable production code.  Django must be
configured before any DRF serializer class is instantiated.  The __main__
block performs a lightweight in-memory demo using a minimal Django setup so
the file can be executed standalone:

    python 42_drf_serializers_advanced_gaps.py

Dependencies (illustrative — full functionality requires all):
    pip install django djangorestframework drf-writable-nested
"""

# =============================================================================
# 0. MINIMAL DJANGO BOOTSTRAP (for standalone __main__ execution)
# =============================================================================

import os
import sys

# Minimum Django settings required to import and instantiate DRF serializers.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', '__main__')

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
            'rest_framework',
        ],
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
        USE_TZ=True,
    )
    django.setup()


# =============================================================================
# 1. MODELS — minimal representations mirroring the theory's domain
# =============================================================================

from django.db import models, transaction


class Customer(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)

    class Meta:
        app_label = 'contenttypes'  # re-use a built-in app_label for :memory: demo


class Product(models.Model):
    title = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        app_label = 'contenttypes'


class Order(models.Model):
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name='orders'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'contenttypes'


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='items'
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='order_items'
    )
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        app_label = 'contenttypes'


class Enrollment(models.Model):
    """Used to illustrate UniqueTogetherValidator."""
    student = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name='enrollments'
    )
    course_code = models.CharField(max_length=50)

    class Meta:
        app_label = 'contenttypes'
        unique_together = [['student', 'course_code']]


class Book(models.Model):
    """Used to illustrate ListSerializer bulk_create."""
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)

    class Meta:
        app_label = 'contenttypes'


class Category(models.Model):
    """Used to illustrate SerializerMethodField N+1 and the annotation fix."""
    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'contenttypes'


class Post(models.Model):
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=20, default='draft')
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, related_name='posts'
    )

    class Meta:
        app_label = 'contenttypes'


# =============================================================================
# 2. PART 1 — WRITABLE NESTED SERIALIZERS
# =============================================================================

from rest_framework import serializers
from rest_framework.validators import UniqueValidator, UniqueTogetherValidator


# -----------------------------------------------------------------------------
# 2a. Child serializer for OrderItem
#     The `id` field is declared explicitly and made optional so the match-by-id
#     update strategy can receive existing PKs from the client payload.
# -----------------------------------------------------------------------------

class OrderItemSerializer(serializers.ModelSerializer):
    # CRITICAL: ModelSerializer marks `id` as read-only by default.
    # Without this override, the PK never appears in validated_data, so every
    # item in a PUT/PATCH payload looks like a "new" item — creating duplicates.
    id = serializers.IntegerField(required=False)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price']


# -----------------------------------------------------------------------------
# 2b. Strategy A — replace-all nested update
#     Simple: delete all existing children and bulk-recreate them from the
#     payload.  Appropriate when children are pure value-objects with no
#     external FK or audit references pointing at them.
# -----------------------------------------------------------------------------

class OrderSerializerReplaceAll(serializers.ModelSerializer):
    """Writable nested Order serializer — replace-all update strategy."""

    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = ['id', 'customer', 'items']

    @transaction.atomic
    def create(self, validated_data):
        """
        Manual create() is mandatory — DRF deliberately does NOT implement
        writable nested creation because the ordering, transaction semantics,
        and FK assignment are inherently ambiguous.

        Pattern:
          1. Pop nested data FIRST (before passing kwargs to parent .create()).
             If 'items' stays in validated_data, Order.objects.create() will
             receive a keyword argument that is not a model field and raise
             TypeError.
          2. Create the parent so its PK is available.
          3. Create children, injecting the parent FK manually.
          4. Wrap everything in a single transaction — a crash after step 2 but
             before step 3 completes would leave an orphaned Order row.
        """
        items_data = validated_data.pop('items')                 # step 1: pop

        order = Order.objects.create(**validated_data)           # step 2: parent

        OrderItem.objects.bulk_create([                          # step 3: children
            OrderItem(order=order, **item) for item in items_data
        ])
        # Note: bulk_create skips model.save() and pre/post_save signals.
        # If those signals matter (e.g. search-index update), use a for-loop
        # with OrderItem.objects.create(order=order, **item) instead.

        return order

    @transaction.atomic
    def update(self, instance, validated_data):
        """Replace-all: delete existing children and recreate from payload."""
        items_data = validated_data.pop('items', None)

        # Update flat fields on the parent instance.
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            # None means the client did not include 'items' at all (PATCH);
            # an empty list [] means the client explicitly wants zero children.
            instance.items.all().delete()
            OrderItem.objects.bulk_create([
                OrderItem(order=instance, **item) for item in items_data
            ])

        return instance


# -----------------------------------------------------------------------------
# 2c. Strategy B — match-by-id nested update (production-grade)
#     Preserves child PKs so external references (payments, audit logs, FKs
#     from other models) remain valid across updates.
# -----------------------------------------------------------------------------

class OrderSerializerMatchById(serializers.ModelSerializer):
    """Writable nested Order serializer — match-by-id update strategy."""

    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = ['id', 'customer', 'items']

    @transaction.atomic
    def create(self, validated_data):
        """Identical create() logic regardless of update strategy."""
        items_data = validated_data.pop('items')
        order = Order.objects.create(**validated_data)
        for item_data in items_data:
            item_data.pop('id', None)                      # ignore any client-supplied id on create
            OrderItem.objects.create(order=order, **item_data)
        return order

    @transaction.atomic
    def update(self, instance, validated_data):
        """
        Diff-and-merge algorithm:

          - Items with a known id  → UPDATE in-place (preserves FK references).
          - Items without an id or with an unknown id → CREATE as new children.
          - Existing items not mentioned in the payload → DELETE.

        Decision table:
          +--------------------+----------------+------------------------------+
          | Criterion          | Replace-all    | Match-by-id                  |
          +--------------------+----------------+------------------------------+
          | Code complexity    | Minimal        | Diff logic required          |
          | Child PKs stable?  | No (re-keyed)  | Yes (preserved)              |
          | FK/audit refs safe?| No (rows gone) | Yes                          |
          | Signals fired?     | Only if loop   | Yes (per-row save)           |
          | Best for           | Value-objects  | Identity-critical children   |
          +--------------------+----------------+------------------------------+
        """
        items_data = validated_data.pop('items', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            existing = {item.id: item for item in instance.items.all()}
            seen_ids = set()

            for item_data in items_data:
                item_id = item_data.pop('id', None)

                if item_id and item_id in existing:
                    # UPDATE — a payload item matched an existing child by PK.
                    child = existing[item_id]
                    for attr, value in item_data.items():
                        setattr(child, attr, value)
                    child.save()
                    seen_ids.add(item_id)
                else:
                    # CREATE — payload has no id, or an id not in the current set.
                    new_child = OrderItem.objects.create(order=instance, **item_data)
                    seen_ids.add(new_child.id)

            # DELETE — existing children not referenced by the payload.
            instance.items.exclude(id__in=seen_ids).delete()

        return instance


# -----------------------------------------------------------------------------
# 2d. Third-party shortcut: drf-writable-nested
#     Handles the boilerplate above automatically (reverse FK, M2M, direct FK).
#     Use in CRUD-heavy admin APIs where default update semantics are acceptable.
#     In interviews: always explain the manual approach first — jumping straight
#     to the package signals that you do not understand the underlying mechanics.
# -----------------------------------------------------------------------------

# pip install drf-writable-nested
try:
    from drf_writable_nested import WritableNestedModelSerializer  # type: ignore

    class OrderSerializerAutoNested(WritableNestedModelSerializer):
        """
        Drop-in: create() and update() (match-by-id style) are provided FREE
        by the mixin.  Suitable when the default merge semantics match your
        business rules and you accept that a third-party dependency now owns
        your write behaviour.
        """

        items = OrderItemSerializer(many=True)

        class Meta:
            model = Order
            fields = ['id', 'customer', 'items']

except ImportError:
    # Package not installed — skip silently so the rest of the module works.
    pass


# =============================================================================
# 3. PART 2 — VALIDATORS AND VALIDATION ORDER
# =============================================================================

# -----------------------------------------------------------------------------
# 3a. UniqueValidator — explicit field-level uniqueness
#     ModelSerializer auto-generates this from model field unique=True, but you
#     must write it manually when: (a) using plain Serializer, (b) the queryset
#     needs to be scoped (e.g. exclude soft-deleted rows), or (c) you need
#     case-insensitive lookup.
# -----------------------------------------------------------------------------

from django.contrib.auth import get_user_model

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        validators=[
            UniqueValidator(
                queryset=User.objects.filter(is_active=True),   # exclude deactivated accounts
                message='This email address is already registered.',
                lookup='iexact',                                 # case-insensitive uniqueness
            )
        ]
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        # Use create_user() so the password is properly hashed.
        return User.objects.create_user(**validated_data)

    # Key points about UniqueValidator:
    #   - queryset= is REQUIRED; this is where you customise the scope.
    #   - On UPDATE (serializer has an instance), the validator automatically
    #     excludes the instance's own PK — no "duplicate" false-positive on self.
    #   - This is a check-then-act pattern; a DB UniqueConstraint is still
    #     required for correctness under concurrent requests.


# -----------------------------------------------------------------------------
# 3b. UniqueTogetherValidator — composite uniqueness at the object level
#     Fires AFTER all per-field validation succeeds (see the flow diagram below).
#     ModelSerializer auto-generates this from Meta.unique_together / UniqueConstraint
#     without conditions.  Write it manually when using plain Serializer or when
#     you need a custom message / scoped queryset.
# -----------------------------------------------------------------------------

class EnrollmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enrollment
        fields = ['student', 'course_code']
        validators = [
            UniqueTogetherValidator(
                queryset=Enrollment.objects.all(),
                fields=['student', 'course_code'],
                message='This student is already enrolled in the specified course.',
            )
        ]

    # Trap: every field listed in UniqueTogetherValidator becomes implicitly
    # required — the validator cannot run if a field is missing.  In PATCH
    # (partial=True) DRF uses the instance's current values to fill gaps.


# -----------------------------------------------------------------------------
# 3c. Validation ORDER — full pipeline documented in code
#
# serializer.is_valid() triggers run_validation(data), which executes:
#
# [PER FIELD — in declaration order]
#   (a) validate_empty_values()       required / allow_null / default check
#   (b) to_internal_value()           type conversion: "5" → 5, "2024-01-01" → date
#                                     FAIL HERE → validate_<field> never runs
#   (c) run_validators()              field-level validators[] — UniqueValidator HERE
#   (d) validate_<field>(value)       your custom per-field hook
#                                     value is type-guaranteed at this point
#
# Field errors are COLLECTED (not fail-fast across fields) — the client sees
# all field errors in one response.
#
# [OBJECT LEVEL — only if ALL fields pass]
#   (e) validate(attrs)               cross-field logic
#   (f) serializer.validators[]       UniqueTogetherValidator HERE
#       (and Meta.validators[])
#
# Consequence: if any field fails (a)–(d), the object-level (e)–(f) never runs.
# So inside validate() you can safely access required fields without None-checks.
# -----------------------------------------------------------------------------

def _no_profanity(value: str) -> None:
    """Example field-level validator function."""
    blocked = {'badword', 'spam'}
    if any(w in value.lower() for w in blocked):
        raise serializers.ValidationError('Content contains disallowed words.')


class BookingSerializer(serializers.Serializer):
    """
    Demonstrates the full validation pipeline with all four hooks.

    (b) to_internal_value  — DateTimeField converts the raw string.
    (c) run_validators     — _no_profanity runs on 'notes' field.
    (d) validate_notes     — per-field hook; value is already a clean string.
    (e) validate           — cross-field: ends_at must be after starts_at.
    """

    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    notes = serializers.CharField(
        required=False,
        default='',
        validators=[_no_profanity],      # (c) — runs before validate_notes
    )

    def validate_notes(self, value: str) -> str:
        """(d) Per-field hook — value is guaranteed to be a str here."""
        return value.strip().upper()     # transform is allowed in validate_<field>

    def validate(self, attrs: dict) -> dict:
        """(e) Cross-field hook — only reached if all fields passed."""
        if attrs['ends_at'] <= attrs['starts_at']:
            raise serializers.ValidationError(
                {'ends_at': 'End time must be after start time.'}
            )
        return attrs


# =============================================================================
# 4. PART 3 — SERIALIZER CONTEXT, @api_view, LOGIC PLACEMENT
# =============================================================================

# -----------------------------------------------------------------------------
# 4a. get_serializer_context — what GenericAPIView provides by default
#
# Source (rest_framework/generics.py):
#   def get_serializer_context(self):
#       return {'request': self.request, 'format': self.format_kwarg, 'view': self}
#
# The three keys — 'request', 'format', 'view' — are always present when the
# serializer is instantiated through a GenericAPIView or ViewSet.
# When you instantiate a serializer manually (shell, test, Celery task) the
# context dict is EMPTY — always use .get('request') not ['request'] unless
# you are certain the serializer is being called from a view.
# -----------------------------------------------------------------------------

from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle


class PostSerializer(serializers.ModelSerializer):
    """
    Demonstrates three context-dependent patterns:
      1. Pre-fetched set from context  → N+1-free per-object flag.
      2. current user display          → 'You' vs full name.
      3. created_by injection in create().
    """

    is_subscribed = serializers.SerializerMethodField()
    author_display = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ['id', 'title', 'body', 'status', 'is_subscribed', 'author_display']

    def get_is_subscribed(self, obj) -> bool:
        """
        Uses a pre-fetched set injected via get_serializer_context().
        One Python set lookup per object instead of one DB query per object.
        """
        subscriptions: set = self.context.get('user_subscriptions', set())
        return obj.category_id in subscriptions

    def get_author_display(self, obj) -> str:
        """Shows 'You' when the requesting user is the post author."""
        request = self.context.get('request')
        if request is None:
            return ''
        # Defensive: Post.author is not on this minimal model, so return title
        # as a stand-in to keep the demo runnable.
        return obj.title  # real code: obj.author.get_full_name() or 'You'

    def create(self, validated_data):
        """
        Inject request-context data inside create() when needed.
        Prefer perform_create() in the view for injecting current user — see
        section 4b below.  Direct access here is a secondary pattern used when
        the serializer must be self-contained (e.g. used from management commands
        that still provide a fake request object).
        """
        request = self.context.get('request')
        # Example: validated_data['created_by'] = request.user if request else None
        return super().create(validated_data)


class PostViewSet(viewsets.ModelViewSet):
    """
    Shows how to augment the default context with a pre-fetched dataset so that
    PostSerializer.get_is_subscribed() never fires a per-row query.
    """

    queryset = Post.objects.all()
    serializer_class = PostSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()      # keep 'request'/'format'/'view'
        user = self.request.user
        if user.is_authenticated:
            # Pre-fetch ONCE per request; the set is shared across all items in
            # a list response without an extra query per item.
            context['user_subscriptions'] = set(
                user.groups.values_list('id', flat=True)  # stand-in for subscriptions
            )
        else:
            context['user_subscriptions'] = set()
        return context

    def perform_create(self, serializer):
        """
        CORRECT place for request-context injection — view concern stays in the view.
        kwargs passed to serializer.save() are merged into validated_data before
        serializer.create() is called.
        """
        serializer.save()                               # real code: serializer.save(owner=self.request.user)
        # Business-logic side-effects belong in a service layer, not here or in
        # the serializer:
        #   order_service.send_confirmation(serializer.instance)


# -----------------------------------------------------------------------------
# 4b. @api_view — function-based DRF view for one-off RPC-style endpoints
#
# Decorator stacking rule: @api_view MUST be the outermost decorator (written
# topmost in source).  Decorators are applied bottom-up; @permission_classes and
# @throttle_classes only SET attributes on the wrapped function, which the
# APIView wrapper created by @api_view then READS.  If @api_view is not outermost
# those attributes never reach the wrapper and permissions are silently skipped.
# -----------------------------------------------------------------------------

@api_view(['POST'])                          # outermost — last applied, first seen
@permission_classes([IsAuthenticated])
@throttle_classes([UserRateThrottle])
def resend_verification_email(request):
    """
    One-off action endpoint — @api_view is the right choice here.
    A ViewSet with a single @action would add routing ceremony for no benefit.
    """
    # request is a DRF Request object; request.data and request.user work normally.
    # request.user.send_verification()   # real implementation
    return Response({'detail': 'Verification email sent.'}, status=202)


# Logic placement decision matrix (summary):
#
#   Request-context injection (current user, client IP)
#     → view.perform_create() via serializer.save(owner=request.user)
#     Reason: keeps serializer decoupled from HTTP Request; reusable in tests.
#
#   Object construction (nested pops, derived defaults, M2M setup)
#     → serializer.create() / serializer.update()
#     Reason: construction logic is the same regardless of which view calls it.
#
#   Business logic (payment charge, email, inventory decrement, search indexing)
#     → service layer function called from perform_create / Celery / management cmd
#     Reason: must be callable outside HTTP — scheduler, admin action, CLI.
#
#   HTTP concerns (custom status code, Location header)
#     → view.create() override


# =============================================================================
# 5. PART 4 — N+1 IN LISTS, ListSerializer INTERNALS, BULK, DYNAMIC FIELDS
# =============================================================================

from django.db.models import Count, Q


# -----------------------------------------------------------------------------
# 5a. SerializerMethodField N+1 — anti-pattern and fix
# -----------------------------------------------------------------------------

class CategorySerializerBad(serializers.ModelSerializer):
    """
    ANTI-PATTERN: fires one COUNT query per Category object in a list.
    50 categories = 51 queries.  select_related does NOT help here because
    .count() always issues a fresh aggregate query regardless of prefetching.
    """

    post_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'post_count']

    def get_post_count(self, obj) -> int:
        # One SELECT COUNT(*) per row — N+1.
        return obj.posts.filter(status='published').count()


class CategorySerializer(serializers.ModelSerializer):
    """
    CORRECT: reads from a queryset annotation that was computed in a single
    GROUP BY query on the view side.

    View queryset:
        Category.objects.annotate(
            post_count=Count('posts', filter=Q(posts__status='published'))
        )

    The defensive getattr fallback allows this serializer to be used in the
    Django shell or tests without a pre-annotated queryset.
    """

    post_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'post_count']

    def get_post_count(self, obj) -> int:
        # Fast path: annotation is present (view provided it).
        # Fallback: single-object context where annotation was not applied.
        return getattr(obj, 'post_count', obj.posts.filter(status='published').count())


# Rule: never write an ORM call inside a SerializerMethodField that will be
# used in a list response.  Options:
#   (1) Annotate on the queryset  → one GROUP BY for all rows.
#   (2) Inject pre-fetched data via context  → Part 3 pattern.
#   (3) prefetch_related + Python-side filter  → works for relations,
#       not aggregates.


# -----------------------------------------------------------------------------
# 5b. many=True / ListSerializer internals
#
# PostSerializer(queryset, many=True)
#   → __new__ intercepts the call
#   → many_init() is invoked
#   → returns ListSerializer(child=PostSerializer(), ...)
#
# ListSerializer.data property:
#   [child.to_representation(item) for item in self.instance]
#
# Cost at scale: 1000 objects × 15 fields = 15 000 to_representation calls.
# Profiling routinely shows serialization taking MORE time than the DB query.
#
# Mitigation levers:
#   1. Eliminate N+1 (most impactful) — select_related / prefetch_related.
#   2. Always paginate — never serialize an unbounded queryset.
#   3. Use a lean list serializer and a full detail serializer — choose via
#      get_serializer_class(self.action == 'list').
#   4. Extreme: qs.values() + plain dict response, bypass serializer entirely.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# 5c. Custom ListSerializer — bulk_create for a bulk-insert endpoint
# -----------------------------------------------------------------------------

class BookListSerializer(serializers.ListSerializer):
    """
    Overrides create() to use bulk_create, collapsing N individual INSERT
    statements into a single multi-row VALUES clause.

    Trade-offs vs a per-item loop:
      + One DB round-trip instead of N.
      - model.save() is NOT called; pre_save / post_save signals are skipped.
      - M2M relations are not set by bulk_create — handle separately.
      - If post_save signals drive cache / search-index updates you must
        trigger those explicitly after bulk_create.
    """

    def create(self, validated_data: list) -> list:
        books = [Book(**item) for item in validated_data]
        return Book.objects.bulk_create(books)


class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ['id', 'title', 'author']
        list_serializer_class = BookListSerializer   # used automatically when many=True


class BulkCreateMixin:
    """
    Composable ViewSet mixin that exposes POST /resource/bulk_create/.
    Usage:
        class BookViewSet(BulkCreateMixin, viewsets.ModelViewSet):
            queryset = Book.objects.all()
            serializer_class = BookSerializer
    """

    from rest_framework.decorators import action as drf_action

    @drf_action(detail=False, methods=['POST'])
    def bulk_create(self, request):
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=201)


# -----------------------------------------------------------------------------
# 5d. DynamicFieldsModelSerializer — ?fields=id,title query-param pruning
#     Official DRF docs recipe, enhanced to support both kwarg and query-param.
#
# Advantage over a to_representation override: fields are removed during
# __init__, so they are excluded from BOTH validation and serialization —
# not just the output.  This matters when the pruned fields are expensive
# nested serializers or SerializerMethodFields.
#
# many=True note: when using the query-param path the context['request'] is
# forwarded to the child by ListSerializer automatically, so pruning works
# consistently in list responses without extra wiring.
# -----------------------------------------------------------------------------

class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    Base serializer that supports field-level pruning via:
      - Explicit kwarg:   PostSerializer(post, fields=['id', 'title'])
      - Query parameter:  GET /posts/?fields=id,title

    Subclasses simply inherit this and declare their Meta as usual.
    """

    def __init__(self, *args, **kwargs):
        # Pop 'fields' before calling super().__init__ so it is not passed
        # through to ModelSerializer, which would raise a TypeError.
        requested_fields = kwargs.pop('fields', None)
        super().__init__(*args, **kwargs)

        if requested_fields is None:
            # Fall back to the request query parameter.
            request = self.context.get('request')
            if request:
                param = request.query_params.get('fields')
                if param:
                    requested_fields = [f.strip() for f in param.split(',')]

        if requested_fields is not None:
            allowed = set(requested_fields)
            # self.fields is a lazy BindingDict — mutating it in __init__ is safe.
            for field_name in set(self.fields) - allowed:
                self.fields.pop(field_name)


class PostDynamicSerializer(DynamicFieldsModelSerializer):
    """
    GET /posts/          → all fields
    GET /posts/?fields=id,title  → only id and title (body, status skipped)
    Python:  PostDynamicSerializer(post, fields=['id', 'title'])
    """

    class Meta:
        model = Post
        fields = ['id', 'title', 'body', 'status']


# =============================================================================
# 6. COMMON PITFALLS — reference comments for quick review
# =============================================================================

"""
PITFALL 1 — Forgot to override create() for writable nested serializer.
  is_valid() passes (validation runs fine); .save() raises:
  "The `.create()` method does not support writable nested fields by default."
  Validation and persistence are separate phases — do not conflate them.

PITFALL 2 — Nested data not popped before parent create().
  Order.objects.create(**validated_data) with 'items' still in the dict raises
  TypeError: unexpected keyword argument.  Pop FIRST.

PITFALL 3 — Left child `id` as read-only in match-by-id update.
  `id` never appears in validated_data → every item looks new → duplicates on
  every PUT.  Fix: id = serializers.IntegerField(required=False) in the child.

PITFALL 4 — No @transaction.atomic on nested create/update.
  Crash after parent is created but before all children finish → orphaned parent
  row with partial data.  Always wrap nested write methods in a transaction.

PITFALL 5 — Wrong @api_view decorator order.
  @permission_classes above @api_view → api_view wrapper never sees the
  permission attribute → permissions silently skipped.
  @api_view must be the TOPMOST (outermost) decorator.

PITFALL 6 — Hard-indexing context: self.context['request'].
  In Celery tasks, Django shell, or unit tests the serializer has no view —
  context is an empty dict → KeyError.  Always use self.context.get('request').

PITFALL 7 — ORM query inside SerializerMethodField on a list endpoint.
  Each call fires a query → N+1.  Annotate on the queryset or inject
  pre-fetched data through context instead.

PITFALL 8 — Treating UniqueValidator as the uniqueness guarantee.
  It is a check-then-act pattern with a race window.  DB UniqueConstraint
  (or unique=True on the model field) is required for correctness.  Catch
  IntegrityError in the view to handle the rare concurrent-insert case.

PITFALL 9 — Cross-field logic written in validate_<field> instead of validate().
  Single-field rules belong in validate_<field> — the error is mapped to the
  correct field name.  Cross-field rules must go in validate() where all attrs
  are available; placing them in a per-field hook means the other field's value
  may not have passed validation yet.

PITFALL 10 — Ignoring bulk_create signal omissions.
  If a post_save signal updates a search index or invalidates a cache, bulk_create
  bypasses it silently.  Either switch to a for-loop or call the side-effect
  logic explicitly after bulk_create returns.
"""


# =============================================================================
# 7. __main__ — standalone demo (no external DB required)
# =============================================================================

def _run_demo():
    """
    Illustrates:
      - BookingSerializer validation order (date parsing, per-field hook,
        cross-field check).
      - DynamicFieldsModelSerializer field pruning via explicit kwarg.
      - OrderSerializerReplaceAll validation (no DB — is_valid() only).
    """
    import datetime as dt
    print("=" * 60)
    print("DRF Serializers Advanced Gaps — Demo")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Demo 1: BookingSerializer — validation pipeline
    # ------------------------------------------------------------------
    print("\n[1] BookingSerializer — validation order demo")

    good_data = {
        'starts_at': '2026-06-13T10:00:00Z',
        'ends_at': '2026-06-13T11:00:00Z',
        'notes': 'regular booking',
    }
    s = BookingSerializer(data=good_data)
    valid = s.is_valid()
    print(f"  Valid payload → is_valid(): {valid}")
    if valid:
        # validate_notes transforms to upper-case
        print(f"  notes after validate_notes(): {s.validated_data['notes']!r}")

    bad_order = {
        'starts_at': '2026-06-13T11:00:00Z',
        'ends_at': '2026-06-13T10:00:00Z',   # ends before starts → cross-field error
    }
    s2 = BookingSerializer(data=bad_order)
    valid2 = s2.is_valid()
    print(f"  Inverted times  → is_valid(): {valid2}")
    if not valid2:
        print(f"  Errors: {s2.errors}")

    profanity_data = {
        'starts_at': '2026-06-13T09:00:00Z',
        'ends_at': '2026-06-13T10:00:00Z',
        'notes': 'badword included',           # triggers _no_profanity validator (step c)
    }
    s3 = BookingSerializer(data=profanity_data)
    valid3 = s3.is_valid()
    print(f"  Profanity notes → is_valid(): {valid3}")
    if not valid3:
        print(f"  Errors: {s3.errors}")

    # ------------------------------------------------------------------
    # Demo 2: DynamicFieldsModelSerializer — field pruning via kwarg
    #         (No DB needed — to_representation on an unsaved Post object)
    # ------------------------------------------------------------------
    print("\n[2] DynamicFieldsModelSerializer — kwarg-based field pruning")

    # Instantiate without saving to DB — serializer.data uses to_representation
    # on the instance; it does not call .save().
    post = Post(id=99, title='Hello World', body='Body text', status='published')

    full = PostDynamicSerializer(post)
    print(f"  All fields:       {list(full.data.keys())}")

    lean = PostDynamicSerializer(post, fields=['id', 'title'])
    print(f"  Pruned to id+title: {list(lean.data.keys())}")

    # ------------------------------------------------------------------
    # Demo 3: BookingSerializer error collection (multiple field errors)
    # ------------------------------------------------------------------
    print("\n[3] Error collection — all field errors returned together")

    multi_bad = {
        'starts_at': 'not-a-date',      # fails to_internal_value
        'ends_at': 'also-bad',          # fails to_internal_value
        # 'notes' absent — uses default ''
    }
    s4 = BookingSerializer(data=multi_bad)
    valid4 = s4.is_valid()
    print(f"  Two bad dates → is_valid(): {valid4}")
    print(f"  Errors (both fields reported): {s4.errors}")

    print("\n" + "=" * 60)
    print("Demo complete.")
    print("=" * 60)


if __name__ == '__main__':
    # Create tables for the in-memory SQLite database so ORM model attrs
    # resolve correctly during serializer field introspection.
    from django.test.utils import setup_test_environment
    setup_test_environment()

    from django.db import connection
    with connection.schema_editor() as schema_editor:
        for model_class in [Customer, Product, Order, OrderItem, Enrollment, Book, Category, Post]:
            try:
                schema_editor.create_model(model_class)
            except Exception:
                pass  # table may already exist if models share contenttypes app_label

    _run_demo()
