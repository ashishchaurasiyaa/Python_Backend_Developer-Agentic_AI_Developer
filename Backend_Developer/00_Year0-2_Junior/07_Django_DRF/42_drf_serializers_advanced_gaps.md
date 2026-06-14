# DRF Serializers Advanced Gaps — Writable Nested, Validation Order, Context, ListSerializer, Dynamic Fields

## Why It Matters

Serializers DRF ka **heart** hain — aur interview me sabse zyada grilling yahi hoti hai. "Nested serializer me POST karo to kya hota hai?" pe 80% candidates atak jaate hain, kyunki DRF **by default writable nested support hi nahi karta** — aur "kyun nahi karta" ka jawab dena hi senior vs junior ka difference hai.

Interview reality:
- "Order create karte waqt items bhi saath aaye — serializer kaise likhoge?" → writable nested create/update
- "validate_email pehle chalta hai ya UniqueValidator?" → validation ORDER (full flow)
- "perform_create me kya daloge, create() me kya?" → logic placement decision
- "List endpoint slow kyun hai?" → SerializerMethodField N+1 + ListSerializer cost

Yeh file Round-2 gaps band karti hai — pehle ki files (02, 18) me serializers basics + nested read covered hai; yahan **writes, validation internals, context, aur bulk** deep me.

---

## Core Concepts — Part 1: Writable Nested Serializers DEEP

### Kyun DRF by-default writable nested support NAHI karta? (THE classic question)

```python
class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)        # nested — READ to free me chalega

    class Meta:
        model = Order
        fields = ['id', 'customer', 'items']


# GET → perfect nested JSON. But POST karo to:
serializer = OrderSerializer(data={'customer': 1, 'items': [{'product': 5, 'quantity': 2}]})
serializer.is_valid()      # True — validation TO ho jaati hai!
serializer.save()
# ❌ raises: "The `.create()` method does not support writable nested fields by default.
#            Write an explicit `.create()` method for serializer OrderSerializer..."
```

**Kyun?** DRF maintainers ka **deliberate design decision** hai (docs me "Because the behavior of nested creates and updates can be ambiguous"). Ambiguity kahaan hai:

1. **Create me:** nested item pehle banaya jaaye ya parent? FK kab assign ho? Agar 3rd item fail ho jaaye to pehle 2 ka kya (transaction)?
2. **Update me aur bhi worse:** PUT me `items` aaye to — purane items **delete** karein? **Match-by-id update** karein? Naye **append** karein? Teeno valid strategies hain, **DRF tumhare liye guess nahi karega**. Implicit magic se explicit error better hai — "explicit is better than implicit."
3. **Relations complexity:** reverse FK vs M2M vs through-model — har case ka create flow alag hai.

Isliye DRF bolta hai: **tum batao kya karna hai** — `create()`/`update()` override karo.

### Manual create() override — nested pop + objects create

```python
class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = ['id', 'customer', 'items']

    def create(self, validated_data):
        # STEP 1: nested data POP karo — warna Order.objects.create(items=[...]) pe
        #         TypeError aayega ('items' is not a direct field of Order)
        items_data = validated_data.pop('items')

        # STEP 2: parent pehle banao (FK ke liye parent ka pk chahiye)
        order = Order.objects.create(**validated_data)

        # STEP 3: children banao, FK manually set karke
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)
        # (Better: OrderItem.objects.bulk_create([...]) — 1 query, but signals/auto_now skip hote hain)

        return order
```

**Transaction lagao!** Item #3 fail hua to Order + 2 items orphan reh jaayenge:

```python
    from django.db import transaction

    @transaction.atomic            # ya view me ATOMIC_REQUESTS — but serializer self-contained better
    def create(self, validated_data):
        ...
```

### update() override — replace-all vs match-by-id (interview favourite)

**Strategy A: Replace-all (delete + recreate)** — simple, but destructive:

```python
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)

        # Parent ke flat fields update
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:                  # None = client ne items bheja hi nahi (PATCH)
            instance.items.all().delete()           # purane SAB delete
            OrderItem.objects.bulk_create([
                OrderItem(order=instance, **item) for item in items_data
            ])
        return instance
```

**Strategy B: Match-by-id (diff & merge)** — production-grade, ids preserve hote hain:

```python
class OrderItemSerializer(serializers.ModelSerializer):
    # CRITICAL: id by default read-only hota hai → validated_data me AATA HI NAHI!
    # Match-by-id ke liye explicitly writable banao:
    id = serializers.IntegerField(required=False)

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = ['id', 'customer', 'items']

    @transaction.atomic
    def update(self, instance, validated_data):
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
                    # UPDATE — id match hua
                    item = existing[item_id]
                    for attr, value in item_data.items():
                        setattr(item, attr, value)
                    item.save()
                    seen_ids.add(item_id)
                else:
                    # CREATE — naya item (id nahi bheja ya unknown)
                    new = OrderItem.objects.create(order=instance, **item_data)
                    seen_ids.add(new.id)

            # DELETE — jo payload me nahi aaye woh remove
            instance.items.exclude(id__in=seen_ids).delete()

        return instance
```

| | Replace-all | Match-by-id |
|---|---|---|
| Code complexity | Simple (3 lines) | Diff logic chahiye |
| Child ids stable? | ❌ Naye ids har update pe | ✅ Preserve hote hain |
| Child pe FK/audit refs? | ❌ TOOT jaayenge (deleted rows!) | ✅ Safe |
| Signals/auto fields | bulk_create skip karta hai | Per-row save → sab chalta hai |
| Kab use karo | Children pure value-objects hon (tags, address lines) | Children ki identity matter kare (items with payments/refs) |

### many=True nested writes — kya dhyan rakhna

- `items = OrderItemSerializer(many=True)` likhne pe DRF internally **`ListSerializer(child=OrderItemSerializer())`** banata hai (Part 4 me detail).
- Validation **per-child** chalti hai — errors bhi list-shaped aate hain: `{'items': [{}, {'quantity': ['required']}]}` — index-aligned, isliye client ko pata chalta hai kaunsa item fail hua.
- Nested `many=True` me child ka `id` writable banana (match-by-id) ke alawa, `min_length`/`max_length` bhi laga sakte ho: `OrderItemSerializer(many=True, allow_empty=False)`.

### drf-writable-nested package — jab boilerplate nahi likhna

```python
# pip install drf-writable-nested
from drf_writable_nested import WritableNestedModelSerializer

class OrderSerializer(WritableNestedModelSerializer):
    items = OrderItemSerializer(many=True)
    class Meta:
        model = Order
        fields = ['id', 'customer', 'items']
# create + update (match-by-id style) FREE — reverse FK, M2M, direct FK sab handle.
```

**Kab use karo / na karo:** CRUD-heavy admin-jaisi APIs me time bachata hai. But (1) magic hai — update semantics package decide karta hai, tumhari business need se match na kare to fight karna padta hai; (2) deep nesting me query count explode ho sakta hai. **Interview me pehle manual approach batao, phir package mention karo** — directly package bologe to lagta hai underlying samajh nahi hai.

---

## Core Concepts — Part 2: Validators + Validation ORDER

### UniqueValidator — queryset= kyun mandatory, kab khud lagana padta hai

```python
from rest_framework.validators import UniqueValidator

class UserSerializer(serializers.ModelSerializer):
    # ModelSerializer model field ke unique=True se yeh AUTO-generate karta hai.
    # Khud KAB lagana padta hai? Jab field model se nahi map hota ya queryset customize karni ho:
    email = serializers.EmailField(
        validators=[UniqueValidator(
            queryset=User.objects.filter(deleted_at__isnull=True),  # soft-deleted ignore!
            message='Yeh email already registered hai.',
            lookup='iexact',                                        # case-insensitive check
        )]
    )
```

- **`queryset=` required hai** — validator ko batana padta hai *kahaan* uniqueness check karni hai. Yahi customization point bhi hai (tenant-scoped, alive-only).
- **Update pe smart hai:** serializer me `instance` ho to validator `qs.exclude(pk=instance.pk)` karta hai — apne hi email se "duplicate" error nahi aata.
- **Race condition disclaimer:** yeh bhi check-then-act hai (SELECT phir INSERT) — concurrency me DB `UniqueConstraint` hi final guarantee hai (detail file 38 me). Validator = friendly error, constraint = correctness.

### UniqueTogetherValidator — composite uniqueness serializer-level

```python
from rest_framework.validators import UniqueTogetherValidator

class EnrollmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enrollment
        fields = ['student', 'course']
        validators = [
            UniqueTogetherValidator(
                queryset=Enrollment.objects.all(),
                fields=['student', 'course'],
                message='Student already enrolled in this course.',
            )
        ]
# ModelSerializer model ki Meta.constraints (UniqueConstraint without condition) /
# unique_together se yeh AUTO bana deta hai. Khud tab likho jab plain Serializer use kar rahe ho
# ya message/queryset customize karna ho.
# Trap: ismein involved saare fields required ban jaate hain (warna check ho hi nahi sakta) —
# PATCH me missing field ki value instance se uthata hai.
```

### Validation ORDER — full flow (yeh ratta nahi, samajh ke yaad rakho)

`serializer.is_valid()` → `run_validation(data)` ka exact flow:

```
serializer.is_valid()
   │
   ▼
[PER FIELD — har field ke liye, declaration order me]
   1. field.run_validation(primitive_value)
        a. validate_empty_values()      → required/allow_null/default check
        b. to_internal_value()          → TYPE conversion ("5" → 5, "2024-01-01" → date)
                                          fail → yahi ruk gaya, aage kuch nahi chalega
        c. run_validators()             → field ke validators[] (UniqueValidator YAHAN!)
   2. serializer.validate_<field_name>(value)   → tumhara custom per-field hook
   │
   │   (koi bhi field fail → us field ki error collect, BAAKI fields phir bhi process hote hain —
   │    isliye response me saare field errors EK SAATH aate hain)
   │
   ▼  (sab fields pass hue tabhi object-level chalega!)
[OBJECT LEVEL]
   3. serializer.validate(attrs)                → cross-field logic (start < end etc.)
   4. Meta.validators / serializer.validators[] → UniqueTogetherValidator YAHAN
   │
   ▼
serializer.validated_data ready → ab .save() allowed
```

**Key takeaways:**
- `to_internal_value` fail → us field ka `validate_<field>` **kabhi nahi chalega** — type guarantee mil chuki hoti hai jab tumhara hook chalta hai.
- **`UniqueValidator` (field-level) `validate_<field>` se PEHLE chalta hai**; `UniqueTogetherValidator` (object-level) sabse end me.
- Ek bhi field-level error ho to **object-level `validate()` chalega hi nahi** — isliye `validate()` me `attrs.get('x')` pe None-check ki zaroorat nahi *required* fields ke liye.
- Errors field-level pe **collect** hote hain (fail-fast nahi across fields) — UX ke liye: client ko poori error list ek request me milti hai.

```python
class BookingSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField()                    # (1b) type check
    ends_at = serializers.DateTimeField()
    code = serializers.CharField(validators=[no_profanity])    # (1c) field validators

    def validate_code(self, value):                            # (2) — value guaranteed str
        return value.upper()                                   # transform bhi kar sakte ho!

    def validate(self, attrs):                                 # (3) — cross-field
        if attrs['ends_at'] <= attrs['starts_at']:
            raise serializers.ValidationError({'ends_at': 'End must be after start.'})
        return attrs
```

---

## Core Concepts — Part 3: Context, @api_view, Logic Placement

### get_serializer_context — default kya hai, custom kaise

`GenericAPIView.get_serializer_context()` default me **3 cheezein** deta hai:

```python
# rest_framework/generics.py (source):
def get_serializer_context(self):
    return {'request': self.request, 'format': self.format_kwarg, 'view': self}
```

```python
class PostViewSet(viewsets.ModelViewSet):
    def get_serializer_context(self):
        context = super().get_serializer_context()      # request/format/view RAKHO
        context['user_subscriptions'] = (               # custom: pre-fetched data inject
            set(self.request.user.subscriptions.values_list('category_id', flat=True))
            if self.request.user.is_authenticated else set()
        )
        return context


class PostSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    author_name = serializers.SerializerMethodField()

    def get_is_subscribed(self, obj):
        # ✅ Context se PRE-FETCHED set — per-object query NAHI (N+1 avoided!)
        return obj.category_id in self.context['user_subscriptions']

    def get_author_name(self, obj):
        # Classic pattern: current user context se
        request = self.context.get('request')           # .get() — manual instantiation safe
        if request and request.user == obj.author:
            return 'You'
        return obj.author.get_full_name()

    def create(self, validated_data):
        # self.context['request'].user — serializer ke andar current user
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)
```

**Traps:** (1) Manually `PostSerializer(post)` banaya (test/shell/Celery me) to context **EMPTY** dict hota hai — `self.context['request']` KeyError! Isliye `.get('request')` + None-handle, ya explicitly pass karo: `PostSerializer(post, context={'request': request})`. (2) `practical/blog/serializers.py` ka `get_avatar_url` yahi pattern hai — `request.build_absolute_uri()` ke liye context ka request chahiye.

### @api_view — FBV-style DRF as a real tool (sirf shortcut nahi)

```python
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

@api_view(['POST'])                          # ← sirf POST; baaki pe 405 Method Not Allowed
@permission_classes([IsAuthenticated])       # ← ORDER MATTERS: api_view SABSE UPAR (last applied)
@throttle_classes([UserRateThrottle])
def resend_verification_email(request):
    request.user.send_verification()         # request = DRF Request (request.data works)
    return Response({'detail': 'Sent.'}, status=202)
```

**Decorator stacking ka rule:** `@api_view` **sabse upar** hona chahiye — decorators bottom-up apply hote hain, aur `permission_classes`/`throttle_classes` sirf function pe attributes set karte hain jo `api_view` ka banaya APIView wrapper read karta hai. `api_view` neeche likh doge to attributes wrapper tak pahunchte hi nahi → permissions **silently skip**!

**Kab ViewSet se better:**

| Scenario | Use |
|---|---|
| Full CRUD on a resource | ViewSet (router, kam code) |
| One-off action endpoint (`/resend-email/`, `/health/`, webhook receiver) | `@api_view` — ViewSet ka ceremony overkill |
| RPC-style endpoint jo kisi model se map nahi hota | `@api_view` |
| Custom action on existing resource | ViewSet `@action` (URL resource ke neeche rahe) |

### perform_create vs serializer.save() vs create() — WHERE to put logic

Flow samjho: `view.create()` → `serializer.is_valid()` → `view.perform_create(serializer)` → `serializer.save(**kwargs)` → `serializer.create(validated_data)` (ya `update`).

`serializer.save(owner=x)` me diye kwargs **validated_data me merge** ho jaate hain — yahi injection ka mechanism hai.

| Logic type | Kahaan daalo | Example | Kyun |
|---|---|---|---|
| Request-context injection (current user, IP) | `view.perform_create()` | `serializer.save(owner=self.request.user)` | Serializer ko request se decouple rakho — woh data layer hai |
| Object construction (nested, M2M, defaults derivation) | `serializer.create()/update()` | items pop + bulk create | Reusable — har view/test/script me same construction |
| Pure business logic (payment charge, email, inventory) | **Service layer** function | `order_service.place_order(...)` jo view/serializer dono se call ho | Celery task / management command / admin se bhi chalna chahiye — HTTP se independent |
| Response-side tweak (header, 202 vs 201) | view `create()` override | `Location` header | HTTP concern = view concern |

```python
class OrderViewSet(viewsets.ModelViewSet):
    def perform_create(self, serializer):
        # ✅ View-level: request-derived cheezein inject
        order = serializer.save(customer=self.request.user)
        # ✅ Service-layer call (business logic serializer me MAT thunso):
        order_service.send_confirmation(order)
# (SOLID_Principles.md ka AuditMixin yahi pattern hai — perform_create me created_by inject.)
```

**Smell test:** serializer ke `create()` me `self.context['request']` dikh raha hai bar-bar → woh logic `perform_create` me hona chahiye tha. View me object-construction loops dikh rahe hain → serializer me jaana chahiye tha.

---

## Core Concepts — Part 4: SerializerMethodField N+1, ListSerializer, Bulk, Dynamic Fields

### SerializerMethodField N+1 — the lesson

`practical/blog/serializers.py` ka `CategorySerializer.get_post_count` dekho — woh **fixed version** hai. Anti-pattern yeh hota:

```python
class CategorySerializer(serializers.ModelSerializer):
    post_count = serializers.SerializerMethodField()

    def get_post_count(self, obj):
        return obj.posts.filter(status='published').count()   # ❌ HAR category pe 1 COUNT query!
# 50 categories list endpoint = 1 (list) + 50 (counts) = 51 queries. Page slow, DB on fire.
# select_related/prefetch_related bhi YAHAN nahi bachayega — .count() har object pe fresh query hai.
```

**Fix: queryset pe annotate, method field me annotation read:**

```python
# views.py
def get_queryset(self):
    return Category.objects.annotate(
        post_count=Count('posts', filter=Q(posts__status='published'))
    )                                                          # ✅ EK query, GROUP BY ke saath

# serializers.py — practical/blog/serializers.py ka actual defensive pattern:
def get_post_count(self, obj) -> int:
    return getattr(obj, 'post_count', obj.posts.filter(...).count())
    # annotation hai to use karo; nahi to fallback query (shell/test me serializer akela chale)
```

**Rule:** SerializerMethodField ke andar **kabhi ORM query mat likho** jo list me serialize hoga. Ya annotate karo, ya context me pre-fetched data inject karo (Part 3 ka `user_subscriptions` pattern), ya `prefetch_related` + python-side filter.

### many=True / ListSerializer internals — list slow kyun hoti hai

```python
PostSerializer(qs, many=True)
# Internally __new__ intercept hota hai → many_init() → banta hai:
# ListSerializer(child=PostSerializer(), ...)
# .data pe: [child.to_representation(item) for item in iterable]  ← plain Python loop
```

**Cost samjho:** 1000 objects × 15 fields = 15,000 `to_representation` calls + har SerializerMethodField ka function call + har nested serializer ka apna loop. Profiling me serialization aksar **DB se zyada time** kha jaati hai badi lists pe. Levers:

1. **N+1 in lists** — yahi sabse bada killer: nested `author = AuthorSummarySerializer()` + no `select_related('author')` → 1000 author queries. List endpoints me queryset hamesha `select_related`/`prefetch_related` ke saath (file 15 me detection tools).
2. **Pagination** — unbounded list serialize hi mat karo.
3. **Lean serializer for lists** — list view me chhota serializer (`get_serializer_class` me `self.action == 'list'` check), detail me full.
4. Extreme cases: `qs.values()` + plain dict response, serializer bypass.

### ListSerializer bulk operations — custom create for bulk endpoint

`many=True` ke saath `serializer.save()` default me **per-item child.create() loop** chalata hai — N INSERTs. Bulk endpoint ke liye `ListSerializer.create` override:

```python
class BookListSerializer(serializers.ListSerializer):
    def create(self, validated_data):
        # validated_data = list of dicts (har item child se validated)
        books = [Book(**item) for item in validated_data]
        return Book.objects.bulk_create(books)        # ✅ EK INSERT (multi-row VALUES)
        # Trade-off: save() nahi chalta, pre/post_save signals skip, auto_now_add chalta hai
        # but custom save() logic nahi. M2M bulk_create me set NAHI hota — alag handle karo.


class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ['id', 'title', 'author']
        list_serializer_class = BookListSerializer    # ← many=True pe yeh use hoga


# View side — SOLID_Principles.md (LLD_Theory) ka BulkCreateMixin yahi karta hai:
class BulkCreateMixin:
    @action(detail=False, methods=['POST'])
    def bulk_create(self, request):
        serializer = self.get_serializer(data=request.data, many=True)   # ← many=True explicit
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=201)
# ViewSet me mixin compose karo: class BookViewSet(BulkCreateMixin, ModelViewSet)
# POST /books/bulk_create/ pe JSON array bhejo → ek hi INSERT.
```

**Note:** bulk *update* aur bhi tricky hai (ListSerializer docs khud bolti hain explicit `update()` likho + items ko id se map karo) — pattern wahi Part 1 ka match-by-id, list-level pe.

### Dynamic fields serializer — ?fields= param (init-based filtering)

```python
class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """?fields=id,title,author → sirf yeh fields serialize honge. (DRF docs ka official recipe)"""
    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)            # explicit kwarg se
        super().__init__(*args, **kwargs)

        if fields is None:                             # ya request query param se
            request = self.context.get('request')
            if request:
                fields_param = request.query_params.get('fields')
                fields = fields_param.split(',') if fields_param else None

        if fields is not None:
            allowed = set(fields)
            for field_name in set(self.fields) - allowed:
                self.fields.pop(field_name)            # self.fields = mutable dict — pop = removed


class PostSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = Post
        fields = ['id', 'title', 'body', 'author', 'comments']

# GET /posts/?fields=id,title  → [{"id": 1, "title": "..."}]  — body/comments skip
# Python me: PostSerializer(post, fields=['id', 'title'])
```

**Kyun useful:** mobile clients ko lean payload + heavy fields (nested comments!) skip = serialization cost bhi bachti hai — sirf bandwidth nahi. `practical/blog/serializers.py` me isi ka `to_representation`-based variant hai; `__init__`-based (upar wala) better hai kyunki fields **validation se bhi** hat jaate hain, sirf output se nahi. Trap: `many=True` ke saath kwarg pass karna ho to `ListSerializer` child ko forward karta hai — query-param path zyada reliable hai.

---

## Common Pitfalls

1. **Nested serializer me create() override bhool gaye** — `is_valid()` pass hota hai, `.save()` pe crash. Validation aur save alag phases hain — "validate hua matlab save hoga" assume mat karo.
2. **create() me nested pop nahi kiya** — `Order.objects.create(**validated_data)` me `items` chala gaya → TypeError. Pop FIRST.
3. **Match-by-id update me child `id` read-only chhod diya** — `validated_data` me id aata hi nahi, har item "naya" lagta hai → duplicates. Child me `id = IntegerField(required=False)` declare karo.
4. **Nested create bina transaction** — partial failure pe orphan parent + half children. `@transaction.atomic` on create/update.
5. **`@api_view` decorator order galat** — `@permission_classes` ko `@api_view` ke UPAR likh diya → permissions silently skip. `@api_view` hamesha top pe.
6. **Serializer me `self.context['request']` hard-access** — Celery/test me context empty → KeyError. `.get('request')` + None-path.
7. **SerializerMethodField me query** — list me N+1. Annotate ya context-injection; method field sirf cheap Python compute kare.
8. **UniqueValidator pe bharosa for correctness** — race window hai; DB constraint (file 38) mandatory, validator sirf UX.
9. **`validate()` me field-level kaam** — single-field check `validate_<field>` me rakho (error sahi field pe map hota hai); `validate()` sirf cross-field.
10. **bulk_create ke side effects bhool gaye** — signals/custom save() skip. Agar post_save pe search-index/cache update hota hai to bulk path me explicitly handle karo.

---

## Interview Q&A

**Q1:** DRF by default writable nested serializers support kyun nahi karta?
**A:** Deliberate design — nested writes ka behavior ambiguous hai. Create me ordering/transaction questions, update me 3 valid strategies (replace-all / match-by-id / append) — DRF guess nahi karta, explicit `create()`/`update()` override maangta hai. `.save()` pe clear error deta hai. "Explicit over implicit" — galat silent guess se better hai developer khud semantics define kare.

**Q2:** Writable nested create() kaise likhoge?
**A:** (1) `validated_data.pop('items')` — warna parent create pe TypeError; (2) parent `Order.objects.create(**validated_data)`; (3) children loop/bulk_create me with `order=order` FK; (4) poora `@transaction.atomic` me — partial failure pe rollback. Return parent instance.

**Q3:** Nested update me replace-all vs match-by-id?
**A:** Replace-all: `instance.items.all().delete()` + recreate — simple, but child ids har baar badalte hain (unpe FK/audit refs toot jaate hain). Match-by-id: child serializer me `id` writable banao, existing ko dict me map karo, payload ke id-matched ko update, id-less ko create, unseen ko delete. Identity-critical children (order items with payment refs) = match-by-id; value-object children (tags) = replace-all chalega.

**Q4:** UniqueValidator vs UniqueTogetherValidator vs DB constraint?
**A:** UniqueValidator field-level (queryset= pe check, update pe self-exclude, `lookup='iexact'` possible); UniqueTogetherValidator object-level composite (Meta.validators me, involved fields required ban jaate hain). Dono check-then-act hain — race me fail. DB UniqueConstraint atomic guarantee. Layering: validators for friendly early errors, constraint for correctness, IntegrityError catch for race-window cases.

**Q5:** DRF validation ka exact ORDER?
**A:** Per-field: (a) required/allow_null check → (b) `to_internal_value` (type) → (c) field validators (UniqueValidator yahan) → (d) `validate_<field>`. Saare fields pass hue tab object-level: `validate(attrs)` → serializer/Meta validators (UniqueTogetherValidator). Field errors collect hote hain (sab ek saath response me), but koi bhi field fail ho to object-level chalti hi nahi.

**Q6:** Serializer context me default kya hota hai? Custom kaise pass karte ho?
**A:** GenericAPIView ka `get_serializer_context()` → `{'request', 'format', 'view'}`. Custom: view me method override karke `super()` ke dict me keys add karo. Serializer me `self.context['request'].user` se current user — create() me created_by set ya SerializerMethodField me user-specific output. Manual instantiation me context empty hota hai — `context={'request': request}` khud do ya `.get()` se defensive access.

**Q7:** perform_create vs serializer.create() vs service layer — logic kahaan?
**A:** Request-context injection (current user/IP) → `perform_create(serializer.save(owner=request.user))` — kwargs validated_data me merge hote hain. Object construction (nested writes, derived defaults) → serializer `create()` — reusable across views/tests. Business logic (payments, emails, side effects) → service layer function — Celery/commands/admin se bhi callable, HTTP-independent. View `create()` override sirf HTTP concerns (status, headers) ke liye.

**Q8:** Category list endpoint pe 51 queries aa rahi hain — kya hua, fix?
**A:** `SerializerMethodField` ke `get_post_count` me `obj.posts.count()` — har row pe alag COUNT query = N+1. `select_related` isko nahi bachata (aggregate hai, relation-fetch nahi). Fix: view ke queryset pe `annotate(post_count=Count('posts', filter=Q(...)))` — ek GROUP BY query; serializer me `getattr(obj, 'post_count', fallback)` (practical/blog/serializers.py ka pattern). General rule: method fields me ORM calls list-context me banned.

**Q9:** `many=True` pe internally kya hota hai? Bulk create efficiently kaise?
**A:** `__new__` intercept → `many_init()` → `ListSerializer(child=YourSerializer())`; `.data` = per-item `to_representation` loop, errors index-aligned list. Default `.save()` per-item create (N INSERTs). Bulk: custom `ListSerializer.create` me `bulk_create` (1 INSERT) + child Meta me `list_serializer_class`; view me `get_serializer(data=request.data, many=True)` — BulkCreateMixin `@action` pattern. Caveats: signals/custom save skip, M2M alag handle.

**Q10:** ?fields=id,title se response trim karna ho to?
**A:** DynamicFieldsModelSerializer — `__init__` me `fields` kwarg ya `context['request'].query_params['fields']` read karo, `set(self.fields) - allowed` ko `self.fields.pop()` se hatao. `self.fields` lazy mutable dict hai — init me pop = woh field validate/serialize dono se out. Benefit: lean payload + skipped fields ki serialization cost (nested/method fields!) bhi bachti hai. GraphQL-jaisi flexibility REST me — but contract documentation (OpenAPI) me dhyaan rakho.

---

## References

- [DRF: Writable nested serializers](https://www.django-rest-framework.org/api-guide/serializers/#writable-nested-representations)
- [DRF: Validators (Unique, UniqueTogether)](https://www.django-rest-framework.org/api-guide/validators/)
- [DRF: ListSerializer / customizing multiple create-update](https://www.django-rest-framework.org/api-guide/serializers/#listserializer)
- [DRF: Dynamic fields example (official docs recipe)](https://www.django-rest-framework.org/api-guide/serializers/#dynamically-modifying-fields)
- [drf-writable-nested](https://github.com/beda-software/drf-writable-nested)
- Repo cross-refs: `practical/blog/serializers.py` (get_post_count, avatar context, dynamic fields variant), `38_django_model_inheritance_meta_constraints.md` (DB constraints vs validators race), `15_n_plus_one_detection.md`, `02_Year5+_Senior/.../SOLID_Principles.md` (BulkCreateMixin/AuditMixin)
