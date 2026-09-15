# Django-DRF & FastAPI Framework Q&A

> Format: **Q** → short answer → code → production nuance. Framework rounds test whether you've actually shipped with the framework, not just read the docs. Deep material lives in [`00_Year0-2_Junior/07_Django_DRF/`](../../00_Year0-2_Junior/07_Django_DRF/) (44 topics) and [`06_FastAPI/`](../../00_Year0-2_Junior/06_FastAPI/) (43 topics) — this file condenses both into interview-answer form, Django first, then FastAPI, then a head-to-head comparison section.

---

## SECTION 1 — DJANGO / DRF (Q1–Q14)

### Q1. Explain Django's request lifecycle — what happens between a request arriving and a response leaving?

```
Request → WSGI/ASGI server → Middleware (top-down)
        → URL resolver → View (or DRF ViewSet → Serializer)
        → Middleware (bottom-up, response side)
        → Response
```

Each middleware's `__call__` wraps the next — it can act before calling `get_response(request)` (request-side: auth, CORS, rate-limit) and after (response-side: add headers, log). Deep dive: [`03_django_channels_middleware.md`](../../00_Year0-2_Junior/07_Django_DRF/Django/03_django_channels_middleware.md).

**Follow-up:** *"Where would you add a request-ID for tracing?"* → Custom middleware, early in the stack (before logging middleware), generating a UUID and attaching it to `request` + response headers + log context.

---

### Q2. What's the N+1 query problem, and how do you fix it in Django ORM?

Fetching a list, then querying again **per item** for related data — 1 query becomes N+1.

```python
# BAD — N+1: one query for orders, then one query PER order for its customer
orders = Order.objects.all()
for order in orders:
    print(order.customer.name)   # hits DB every iteration

# FIX — select_related for FK/OneToOne (SQL JOIN, one query)
orders = Order.objects.select_related("customer").all()

# FIX — prefetch_related for M2M/reverse-FK (separate query + Python-side join)
orders = Order.objects.prefetch_related("line_items").all()
```

**How to catch it before prod:** `django-debug-toolbar` in dev, `nplusone` package, or just eyeball the query count in tests with `self.assertNumQueries(N)`. Full detection guide: [`15_n_plus_one_detection.md`](../../00_Year0-2_Junior/07_Django_DRF/Django/15_n_plus_one_detection.md).

---

### Q3. `select_related` vs `prefetch_related` — what's the actual mechanism difference?

| | `select_related` | `prefetch_related` |
|---|---|---|
| Used for | ForeignKey, OneToOne | ManyToMany, reverse FK, GenericRelation |
| Mechanism | SQL `JOIN` — one query | Separate query per relation, joined in Python |
| Why not JOIN for M2M? | Would multiply rows (cartesian product) | Avoids row explosion |

```python
# select_related: one SQL query with JOIN
Book.objects.select_related("author")

# prefetch_related: 2 queries — one for books, one for all related authors (M2M), joined in memory
Book.objects.prefetch_related("authors")
```

---

### Q4. How does Django's ORM build the actual SQL — what's `QuerySet` laziness?

QuerySets are **lazy** — building one (`.filter()`, `.exclude()`, `.order_by()`) doesn't hit the DB. Evaluation is triggered by iteration, `len()`, `list()`, slicing with a step, `bool()`, or `repr()` (e.g. in a debugger/shell).

```python
qs = User.objects.filter(active=True)     # no query yet
qs = qs.filter(age__gte=18)                # still no query — chains just build up
users = list(qs)                            # NOW it hits the DB, once, with combined WHERE clauses
```

**Gotcha:** re-evaluating a QuerySet (e.g., using it in two separate `for` loops) re-runs the query each time unless you cache it (`list(qs)` once, or `qs = list(qs)`). Internals: [`33_queryset_internals.md`](../../00_Year0-2_Junior/07_Django_DRF/Django/33_queryset_internals.md).

---

### Q5. DRF Serializers — what do they actually do, and `Serializer` vs `ModelSerializer`?

Serializers handle **both directions**: Python object → JSON (serialization) and JSON → validated Python data (deserialization), plus validation.

```python
from rest_framework import serializers

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name"]

    def validate_email(self, value):          # field-level validation
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already taken")
        return value

# Deserialize + validate:
serializer = UserSerializer(data=request.data)
serializer.is_valid(raise_exception=True)
user = serializer.save()

# Serialize:
serializer = UserSerializer(user)
serializer.data   # dict, ready for JsonResponse
```

`ModelSerializer` auto-generates fields from the model (less boilerplate); plain `Serializer` when the shape doesn't map 1:1 to a model (aggregated/computed responses, multi-model payloads).

---

### Q6. `APIView` vs `GenericAPIView` + mixins vs `ViewSet`/`ModelViewSet` — when do you pick which?

| | Control | Boilerplate | Use when |
|---|---|---|---|
| `APIView` | Full manual control | Most | Non-CRUD custom logic (e.g. a webhook receiver) |
| `GenericAPIView` + mixins | Compose exact behavior needed | Medium | Need CRUD but want to customize one operation |
| `ModelViewSet` | Full CRUD auto-generated | Least | Standard REST resource, router-registered |

```python
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)   # scope to owner
```

`ModelViewSet` + `router.register()` gives you list/create/retrieve/update/delete for free — trade flexibility for speed. Deep dive: [`07_genericapiview_mixins.md`](../../00_Year0-2_Junior/07_Django_DRF/DRF/07_genericapiview_mixins.md).

---

### Q7. How does DRF authentication differ from permissions? Walk through JWT auth end to end.

**Authentication** answers "who is this?" (identifies the user). **Permissions** answer "can this user do this?" (authorization). They run in sequence — auth first, then permission checks against `request.user`.

```python
# settings.py
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}

class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]   # custom object-level permission
```

```python
class IsOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:      # GET/HEAD/OPTIONS always allowed
            return True
        return obj.owner == request.user         # write only if owner
```

**Follow-up:** *"How do you invalidate a JWT before its expiry (e.g. on logout)?"* → JWTs are stateless by design, so true revocation needs a blocklist (Redis, TTL'd to the token's remaining life) checked in the auth class, or short-lived access tokens + refresh-token rotation so the blast radius of a leaked token is small.

---

### Q8. What are Django signals, and why are senior engineers often wary of them?

Signals (`post_save`, `pre_delete`, custom signals) let decoupled code react to model events without the sender knowing about the listener.

```python
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Order)
def send_confirmation_email(sender, instance, created, **kwargs):
    if created:
        send_email.delay(instance.id)   # dispatch a Celery task
```

**Why be wary:** signals create **implicit, hard-to-trace control flow** — reading `Order.objects.create(...)` gives no hint an email gets sent. In production this causes surprise side effects (double-sends on bulk `.save()` in a loop, signals firing during data migrations, hidden N+1 from signal handlers doing their own queries). Many senior teams prefer explicit service-layer calls over signals for anything with real side effects, reserving signals for logging/cache-invalidation-style concerns. Detail: [`08_internals_signals_async.md`](../../00_Year0-2_Junior/07_Django_DRF/Django/08_internals_signals_async.md).

---

### Q9. How do Django migrations work, and what's the zero-downtime concern with adding a `NOT NULL` column?

Migrations are versioned, ordered Python files describing schema changes, generated by diffing model state (`makemigrations`) and applied with `migrate`. Each migration records its dependency on prior ones, forming a DAG.

**The zero-downtime problem:** adding a `NOT NULL` column without a default **locks the table** while backfilling on large tables, and old app code (mid-deploy) doesn't know about the new required column — breaking writes.

**Safe pattern (expand-contract):**
1. Add column as **nullable** (or with a default) — fast, non-blocking.
2. Backfill existing rows in batches (background job, not in the migration itself for large tables).
3. Deploy app code that writes the new column.
4. Once all rows are backfilled and all app instances updated, add the `NOT NULL` constraint in a follow-up migration.

Full pattern: [`25_zero_downtime_migrations.md`](../../00_Year0-2_Junior/07_Django_DRF/Django/25_zero_downtime_migrations.md), [`26_expand_contract_migrations.md`](../../00_Year0-2_Junior/04_Database_SQL/26_expand_contract_migrations.md).

---

### Q10. Custom User model — why does Django recommend defining one from day one?

Switching the User model **after** the first migration is painful — every FK to `User` and every migration touching auth tables has to be reworked. Even if you don't need custom fields immediately, `AUTH_USER_MODEL = "users.User"` pointing at a thin subclass of `AbstractUser` costs nothing now and avoids a full-project migration later.

```python
class User(AbstractUser):
    phone = models.CharField(max_length=15, blank=True)
    # add fields as needed, later, without a swap-the-model migration
```

---

### Q11. `F()` expressions and `select_for_update` — how do you avoid a race condition on a counter/balance field?

```python
# BAD — race condition: two requests read the same value, both write old_value + 1, one increment is lost
account.balance += 100
account.save()

# FIX — F() pushes the increment into the SQL itself (atomic at the DB level)
from django.db.models import F
Account.objects.filter(id=account.id).update(balance=F("balance") + 100)

# FIX for read-then-branch logic (e.g. "if balance >= amount, debit") — need a row lock:
from django.db import transaction
with transaction.atomic():
    account = Account.objects.select_for_update().get(id=account.id)   # locks the row until commit
    if account.balance >= amount:
        account.balance -= amount
        account.save()
```

`F()` avoids the read-modify-write round trip entirely for simple arithmetic. `select_for_update()` is needed when the logic branches on the current value — it blocks other transactions from reading (for update) that row until this one commits. Full pattern: [`36_f_expressions_atomic_updates.md`](../../00_Year0-2_Junior/07_Django_DRF/Django/36_f_expressions_atomic_updates.md).

---

### Q12. How does DRF pagination work, and cursor vs offset — which for an infinite-scroll feed?

```python
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 20,
}
```

**Offset (`?page=3`)** — simple, but page N requires scanning/skipping N×size rows (slow at scale) and is unstable if rows are inserted/deleted between page loads (items shift, duplicates or skips appear).

**Cursor (`?cursor=eyJ...`)** — encodes a pointer to "the last item you saw" (typically an indexed timestamp/id), so the next page is an indexed range query regardless of dataset size, and stays stable even as new items are inserted. Correct choice for infinite-scroll feeds; offset is fine for small, mostly-static admin-style tables. Full comparison: [`37_pagination_keyset_offset.md`](../../00_Year0-2_Junior/04_Database_SQL/37_pagination_keyset_offset.md).

---

### Q13. How would you test a DRF endpoint that requires authentication?

```python
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

class OrderAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="a@b.com", password="x")
        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_list_orders_scoped_to_user(self):
        Order.objects.create(user=self.user, total=100)
        Order.objects.create(user=User.objects.create_user(email="other@b.com", password="x"), total=200)

        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)   # only the requesting user's order
```

**What interviewers listen for:** testing authorization scoping (not just "does the endpoint return 200"), and using `APITestCase`'s transaction-wrapped test DB rather than hitting a real database.

---

### Q14. Django Channels — when do you actually need it over plain DRF, and what's the core concept?

Channels adds **ASGI-based** support for protocols beyond request/response — WebSockets, long-lived connections, background workers sharing the same codebase as your Django app. Core concept: a `Consumer` (like a View, but for a persistent connection) plus a **channel layer** (usually Redis-backed) for broadcasting messages across multiple server processes/instances.

```python
class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = f"chat_{self.scope['url_route']['kwargs']['room_id']}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def receive(self, text_data):
        await self.channel_layer.group_send(
            self.room_group_name, {"type": "chat_message", "message": text_data}
        )

    async def chat_message(self, event):
        await self.send(text_data=event["message"])
```

**When to reach for it:** real-time chat, live notifications, collaborative editing — anything needing server-push, not just request/response. For simpler cases (occasional live updates), SSE over plain ASGI/FastAPI is often less operational overhead than standing up Channels + a channel layer.

---

## SECTION 2 — FASTAPI (Q15–Q26)

### Q15. What makes FastAPI "fast" — both in dev-speed and runtime?

**Runtime:** built on **Starlette** (ASGI) + **Pydantic** (validation) — async-native, and request validation/serialization is done via compiled Pydantic-core (Rust) rather than manual parsing code. **Dev-speed:** type hints double as validation schema *and* auto-generated OpenAPI docs — one source of truth instead of separately maintaining a schema, validation logic, and API docs.

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Order(BaseModel):
    id: int
    total: float

@app.post("/orders")
async def create_order(order: Order) -> Order:   # this signature IS the validation + the docs
    return order
```

---

### Q16. Explain FastAPI's Dependency Injection system (`Depends`) — why is it better than importing a DB session directly in each route?

```python
from fastapi import Depends

def get_db():
    db = SessionLocal()
    try:
        yield db          # yields the session, code after yield runs on cleanup (like a context manager)
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    user = decode_token_and_fetch(token, db)
    if not user:
        raise HTTPException(401, "Invalid token")
    return user

@app.get("/me")
async def read_me(user: User = Depends(get_current_user)):
    return user
```

**Why it beats a global import:** dependencies are **overridable in tests** (`app.dependency_overrides[get_db] = get_test_db`), automatically documented in OpenAPI, resolved once per request (with caching within that request), and composable — `get_current_user` depends on `get_db`, FastAPI resolves the whole chain. A hardcoded global session can't be swapped per-test or per-tenant without monkeypatching.

---

### Q17. `async def` vs plain `def` route handlers in FastAPI — what actually happens with each?

```python
@app.get("/fast")
async def fast_endpoint():
    await some_async_io()          # runs on the event loop directly

@app.get("/slow")
def sync_endpoint():
    time.sleep(2)                   # blocking, but FastAPI runs `def` routes in a thread pool automatically
```

FastAPI/Starlette runs `def` (sync) path operations in an **external thread pool** so a blocking call inside one doesn't freeze the event loop for everyone else — but that thread pool has a **finite size**, so overwhelming it with many concurrent sync routes still causes queuing. `async def` routes run directly on the event loop — correct when the code inside is genuinely non-blocking (async DB driver, `httpx.AsyncClient`), *wrong and dangerous* if you `await` a call into something that's actually still blocking under the hood.

**Interview trap:** *"Is `async def` always faster?"* → No — an `async def` route that calls a blocking library (sync `requests`, sync psycopg2 driver) blocks the **entire event loop**, which is worse than a `def` route doing the same thing (that at least gets threaded). Deep dive: [`39_async_def_vs_def_threadpool_deep.md`](../../00_Year0-2_Junior/06_FastAPI/39_async_def_vs_def_threadpool_deep.md).

---

### Q18. Pydantic v2 — validators, and the difference between `field_validator` and `model_validator`.

```python
from pydantic import BaseModel, field_validator, model_validator

class SignupRequest(BaseModel):
    password: str
    password_confirm: str
    age: int

    @field_validator("age")
    @classmethod
    def check_age(cls, v):                 # single-field validation
        if v < 18:
            raise ValueError("Must be 18+")
        return v

    @model_validator(mode="after")
    def check_passwords_match(self):        # cross-field validation — needs the whole model
        if self.password != self.password_confirm:
            raise ValueError("Passwords don't match")
        return self
```

`field_validator` when the rule only needs that one field's value. `model_validator` when the rule needs to compare multiple fields together (password confirmation, date-range ordering, conditional-required fields).

---

### Q19. How does FastAPI handle errors, and what's the RFC 7807 "Problem Details" pattern?

```python
from fastapi import HTTPException

@app.get("/orders/{id}")
async def get_order(id: int):
    order = await db.get_order(id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

# Global handler for consistent error shape across the whole API:
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"type": "about:blank", "title": exc.detail, "status": exc.status_code},   # RFC 7807 shape
    )
```

RFC 7807 standardizes error response shape (`type`, `title`, `status`, `detail`, `instance`) so API consumers can handle errors generically instead of parsing ad-hoc error JSON per endpoint. Full pattern: [`21_rfc7807_problem_details.md`](../../00_Year0-2_Junior/06_FastAPI/21_rfc7807_problem_details.md).

---

### Q20. How do you test a FastAPI app, and what does `dependency_overrides` buy you?

```python
from fastapi.testclient import TestClient

def get_test_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = get_test_db    # swap real DB dependency for a test one

client = TestClient(app)

def test_create_order():
    response = client.post("/orders", json={"total": 100})
    assert response.status_code == 201
```

Because dependencies are resolved through `Depends()` rather than imported directly, tests swap out the DB (or auth, or any external client) **without monkeypatching internals** — the route code under test never knows it's talking to a fake. Full pattern: [`labs/08_fastapi_testing_dependency_overrides.py`](../../00_Year0-2_Junior/06_FastAPI/labs/08_fastapi_testing_dependency_overrides.py).

---

### Q21. What's ASGI, and how does it differ from WSGI (why does it matter for FastAPI)?

WSGI is **synchronous**, one request per worker thread/process at a time — no native WebSocket/streaming support. ASGI (Asynchronous Server Gateway Interface) supports async request handling, WebSockets, and long-lived connections natively, with a single worker able to juggle thousands of concurrent connections via the event loop.

```
WSGI:  Client → Gunicorn (sync workers) → Django (sync)
ASGI:  Client → Uvicorn (event loop)     → FastAPI (async) — many connections per worker
```

**Practical consequence:** ASGI servers (Uvicorn/Hypercorn) can serve far more concurrent I/O-bound connections per worker than WSGI, which is why FastAPI/Django-Channels need it for WebSockets and high-concurrency APIs. Internals: [`13_asgi_internals_uvicorn_tuning.md`](../../00_Year0-2_Junior/06_FastAPI/13_asgi_internals_uvicorn_tuning.md).

---

### Q22. Background tasks in FastAPI — `BackgroundTasks` vs offloading to Celery — when do you pick which?

```python
from fastapi import BackgroundTasks

@app.post("/signup")
async def signup(user: UserIn, background_tasks: BackgroundTasks):
    created = await create_user(user)
    background_tasks.add_task(send_welcome_email, created.email)   # runs AFTER response is sent
    return created
```

`BackgroundTasks` runs **in the same process**, after the response is returned — fine for quick, non-critical, fire-and-forget work (an email, a log entry). It has **no retry, no persistence** — if the process crashes or the task raises, the work is silently lost. For anything that must survive a crash, needs retries, or takes more than a second or two, use Celery/RQ with a real broker (Redis/RabbitMQ) instead.

---

### Q23. How do you version a FastAPI API, and what are the trade-offs of each approach?

| Strategy | Example | Trade-off |
|---|---|---|
| URL path | `/v1/orders`, `/v2/orders` | Simple, cacheable, but duplicates routers |
| Header | `Accept: application/vnd.api+json; version=2` | Clean URLs, harder to test/curl casually |
| Query param | `/orders?version=2` | Easy but pollutes query semantics |

```python
v1 = APIRouter(prefix="/v1")
v2 = APIRouter(prefix="/v2")
app.include_router(v1)
app.include_router(v2)
```

**Interview answer:** "Path versioning is the pragmatic default for public APIs — it's explicit, cacheable, and every client/proxy understands it without custom logic. Header versioning is nicer semantically but adds friction for API consumers and debugging."

---

### Q24. What does `HMAC` verification look like for a webhook receiver, and why is it necessary?

```python
import hmac, hashlib

@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    signature = request.headers["Stripe-Signature"]
    expected = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature):    # constant-time comparison — avoids timing attacks
        raise HTTPException(401, "Invalid signature")

    event = json.loads(payload)
    # idempotency: check event["id"] hasn't been processed before (webhooks can be delivered more than once)
```

**Two separate concerns interviewers probe:** (1) signature verification proves the request actually came from the claimed sender, not an attacker POSTing to a guessable URL; (2) idempotency handling, since providers (Stripe, Razorpay) explicitly guarantee **at-least-once** delivery, not exactly-once — duplicate webhook deliveries are expected, not a bug.

---

### Q25. FastAPI rate limiting — how would you implement a per-user sliding-window limiter?

```python
import time
from fastapi import HTTPException

async def rate_limit(user_id: str, redis, limit: int = 100, window: int = 60):
    key = f"rate:{user_id}"
    now = time.time()
    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, now - window)     # drop entries outside the window
    pipe.zadd(key, {str(now): now})
    pipe.zcard(key)                                  # count remaining entries = requests in window
    pipe.expire(key, window)
    _, _, count, _ = await pipe.execute()

    if count > limit:
        raise HTTPException(429, "Rate limit exceeded")
```

A Redis sorted set keyed by timestamp gives an accurate sliding window (unlike a fixed-window counter, which allows bursting 2x the limit right at the window boundary). Full pattern with token-bucket comparison: [`04_rate_limiter`](../../02_Year5+_Senior/01_System_Design/HLD_Code/04_rate_limiter/) and [`LLD_Problems/Rate_Limiter.md`](../../02_Year5+_Senior/01_System_Design/LLD_Problems/Rate_Limiter.md).

---

### Q26. Multi-tenancy in FastAPI — what are the three main isolation strategies, and their trade-offs?

| Strategy | Isolation | Cost | Use when |
|---|---|---|---|
| Separate DB per tenant | Highest | Most ops overhead | Regulated industries, big enterprise tenants |
| Separate schema per tenant | High | Migration complexity scales with tenant count | Mid-size B2B SaaS |
| Shared table + `tenant_id` column | Lowest | Cheapest, but a missing `WHERE tenant_id=` is a data leak | Most SaaS at moderate scale |

```python
# Shared-table approach — tenant scoping enforced at the dependency level, not per-query by hand
async def get_current_tenant(request: Request) -> int:
    return request.state.tenant_id   # set by middleware from subdomain/header/JWT claim

async def get_db_scoped(tenant_id: int = Depends(get_current_tenant), db=Depends(get_db)):
    db.execute(text("SET app.current_tenant = :t"), {"t": tenant_id})   # Postgres RLS enforces it at the DB layer
    return db
```

**Senior-level answer:** "Shared-table is cheapest to run but the riskiest to get wrong — a single missing filter leaks tenant data. Enforce it structurally (Postgres Row-Level Security, or a dependency that always injects the filter) rather than trusting every query author to remember it." Deep dive: [`16_multi_tenant_architecture.md`](../../00_Year0-2_Junior/06_FastAPI/16_multi_tenant_architecture.md).

---

## SECTION 3 — HEAD-TO-HEAD (Q27–Q30)

### Q27. "We're starting a new project — Django+DRF or FastAPI?" How do you actually answer this?

**Lean Django when:** the app is CRUD-and-admin-heavy (internal tools, content-heavy platforms), you want the batteries-included ORM/admin/auth out of the box, and the team is more comfortable with a convention-driven framework.

**Lean FastAPI when:** the service is API-first with no need for a built-in admin, needs async-native performance for high-concurrency I/O (WebSockets, streaming, calling multiple external APIs), or you want type-hint-driven validation/docs as the single source of truth.

**Real-world nuance senior interviewers want to hear:** "It's rarely all-or-nothing — plenty of teams run Django for the admin/ORM-heavy core and a FastAPI service alongside it for a specific high-concurrency or AI-integration workload." Comparison table: [`43_flask_essentials_vs_fastapi.md`](../../00_Year0-2_Junior/06_FastAPI/43_flask_essentials_vs_fastapi.md).

---

### Q28. Both frameworks claim "async support" — what's actually different under the hood?

Django has had `async def` views since 3.1, but the **ORM was sync-only until 4.1's early async QuerySet support**, and even now most third-party Django packages assume sync — mixing async views with the sync ORM means wrapping DB calls in `sync_to_async`, adding overhead. FastAPI is async-native from the ground up (Starlette + an async ORM like SQLAlchemy 2.0's async engine or Tortoise), so there's no sync/async boundary to cross for the common path.

**Practical answer:** "Django's async story is improving but still has sync legacy in the ORM and ecosystem; FastAPI was async-first from day one. If the workload is genuinely async-bound (many concurrent I/O calls per request), FastAPI has less friction today."

---

### Q29. How does dependency injection differ conceptually between the two frameworks?

Django doesn't have a formal DI system — dependencies (DB connections, settings) are typically module-level singletons imported directly, or injected via middleware setting `request.something`. FastAPI's `Depends()` is an explicit, first-class DI graph resolved per-request, testable via `dependency_overrides`.

**Trade-off:** Django's implicit approach is less boilerplate for simple cases but harder to swap in tests without mocking/monkeypatching; FastAPI's explicit graph is more verbose but every dependency is declared, typed, and overridable at the framework level.

---

### Q30. Both support OpenAPI/Swagger — how is the generation different?

FastAPI generates the OpenAPI schema **automatically from the Pydantic models and type hints already in your route signatures** — it's a byproduct of writing normal, typed code, always in sync with the actual validation. DRF needs `drf-spectacular` or `drf-yasg` as a separate layer inspecting serializers/viewsets, which can drift from reality if a serializer's `Meta` doesn't perfectly reflect intended behavior (e.g., a custom `validate()` method the schema generator can't introspect).

**Interview answer:** "FastAPI's docs are structurally guaranteed to match the code because they're generated from the same type hints that do the validation. DRF's are generated by a separate tool inspecting the serializer, which is usually accurate but can drift for anything expressed in custom Python logic rather than declarative fields."

---

**Related:** Django deep topics — [`07_Django_DRF/`](../../00_Year0-2_Junior/07_Django_DRF/). FastAPI deep topics — [`06_FastAPI/`](../../00_Year0-2_Junior/06_FastAPI/). SQL/ORM performance — [`04_Database_SQL/`](../../00_Year0-2_Junior/04_Database_SQL/). API design patterns (versioning, HATEOAS, BFF) — [`02_API_Design/`](../../01_Year3-4_Mid/02_API_Design/).
