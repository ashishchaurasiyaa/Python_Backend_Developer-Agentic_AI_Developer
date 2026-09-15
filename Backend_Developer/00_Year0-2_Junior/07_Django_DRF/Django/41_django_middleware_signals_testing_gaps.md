# Django Middleware Hooks, Lookups, Signals vs save(), Cache, Testing & Deployment Gaps — Round-2 Part 2

## Why It Matters

Yeh file Round-2 audit ke woh gaps band karti hai jo "Django aata hai" aur "Django production me chalaya hai" ke beech ka difference hain:

- **Middleware hooks** — Sentry kaise har exception pakad leta hai bina tumhare views chhue? `process_exception`.
- **`save()` override vs signals** — `update()` ne tumhara override skip kar diya aur audit log ban hi nahi raha. Classic prod bug.
- **`full_clean()` trap** — "maine `clean()` likha tha, phir bhi invalid data DB me kaise gaya?" → `save()` validation call hi nahi karta.
- **`on_commit` test me fire nahi hua** — TestCase rollback karta hai, commit hota hi nahi. Interview me yeh poochte hi hain.

Har section me: real explanation + working code + trap + interview angle.

---

## Core Concepts — Part 1: Middleware Hooks DEEP

### Basic structure recap + saare hooks

```python
class MyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # EK BAAR chalta hai — server start pe. Heavy setup yahan (config load, client init)

    def __call__(self, request):
        # ↓ REQUEST PHASE — view se pehle
        request.start_time = time.monotonic()

        response = self.get_response(request)   # ← chain me agla middleware / view

        # ↑ RESPONSE PHASE — view ke baad
        response['X-Duration-Ms'] = str((time.monotonic() - request.start_time) * 1000)
        return response

    # ===== OPTIONAL HOOKS =====

    def process_view(self, request, view_func, view_args, view_kwargs):
        # URL RESOLVE ke BAAD, view call se PEHLE chalta hai.
        # __call__ ke request-phase me tumhe pata nahi KAUNSA view chalega — yahan pata hai!
        if getattr(view_func, 'skip_audit', False):
            request._skip_audit = True
        return None    # None = continue; HttpResponse = view skip, short-circuit

    def process_exception(self, request, exception):
        # View ne UNCAUGHT exception raise kiya to chalta hai (Http404 bhi).
        # SENTRY YAHIN HOOK KARTA HAI — har error capture, zero view changes.
        error_tracker.capture(exception, extra={'path': request.path})
        return None    # None = Django ka normal 500 handling chale; HttpResponse = custom error page

    def process_template_response(self, request, response):
        # SIRF tab jab response ke paas .render() ho (TemplateResponse) — abhi RENDER NAHI hua!
        # Isliye template/context yahan modify kar sakte ho:
        response.context_data['global_banner'] = get_banner()
        return response   # MUST return response
```

### `process_view` kab use karein

- View function ke **attributes/decorators inspect** karne ho (CSRF middleware exactly yahi karta hai — `@csrf_exempt` ne `view_func.csrf_exempt = True` set kiya hota hai, middleware `process_view` me check karta hai).
- Per-view rate limiting / maintenance mode jisme **resolved view ka naam** chahiye.
- `__call__` ke request-phase me yeh info **nahi** hoti — URL resolution `process_view` se theek pehle hota hai.

### Full hook order diagram — request top-down, response bottom-up

```
settings.MIDDLEWARE = [A, B, C]

REQUEST  ──► A.__call__ (pre)                      ↑ A (post) ──► RESPONSE
                 B.__call__ (pre)              ↑ B (post)
                     C.__call__ (pre)      ↑ C (post)
                         ── URL resolve ──
                         A.process_view → B.process_view → C.process_view   (top-down)
                              ┌────────┐
                              │  VIEW  │
                              └────────┘
                         exception? → C.process_exception → B → A           (bottom-UP)
                         TemplateResponse? → C.process_template_response → B → A (bottom-UP)
```

**Yaad rakhne ka mental model: onion.** Request bahar se andar jaati hai (list order), response andar se bahar (reverse). `process_view` request-side hai → top-down. `process_exception` / `process_template_response` response-side hain → bottom-up.

### Short-circuiting

```python
def __call__(self, request):
    if request.path.startswith('/blocked/'):
        return HttpResponse('Nope', status=403)    # get_response() call hi NAHI kiya
    return self.get_response(request)
```

Middleware `B` ne short-circuit kiya to: `C` ke **dono phases skip**, view skip — lekin `A` ka response-phase **chalega** (request `A` se guzar chuki thi, onion ke bahar nikalte waqt `A` milega hi). Same rule `process_view` ke HttpResponse return pe.

**Trap:** short-circuit ke baad sirf **upar wale** (pehle aaye) middleware response process karte hain. Isliye `SecurityMiddleware` list me **sabse upar** hota hai — har response, short-circuited bhi, uske headers paaye.

---

## Core Concepts — Part 2: Field Lookups Systematic

### Lookup table — yeh poori table fluent honi chahiye

```python
Post.objects.filter(title__iexact='django tips')        # case-insensitive exact
Post.objects.filter(views__gte=100, views__lt=1000)     # chaining = SQL AND
Post.objects.filter(created_at__date=date(2026, 6, 12)) # datetime → sirf date part compare
```

| Lookup | SQL (approx) | Note |
|---|---|---|
| `__exact` | `= 'x'` | Default — `filter(name='x')` == `name__exact` |
| `__iexact` | `ILIKE 'x'` (no %) | Case-insensitive equality |
| `__contains` / `__icontains` | `LIKE '%x%'` / `ILIKE` | **Index use NAHI hota** leading `%` ki wajah se — full scan |
| `__in` | `IN (1,2,3)` | List YA queryset (subquery ban jaata hai) |
| `__gt / __gte / __lt / __lte` | `> >= < <=` | Dates/numbers dono pe |
| `__startswith / __istartswith` | `LIKE 'x%'` | Trailing % — index **use ho sakta hai** |
| `__endswith / __iendswith` | `LIKE '%x'` | Leading % — index nahi |
| `__range=(a, b)` | `BETWEEN a AND b` | **Inclusive dono sides** |
| `__date` / `__year` / `__month` | date extract | DateTimeField pe; `created_at__year=2026` |
| `__isnull=True/False` | `IS NULL` / `IS NOT NULL` | `=None` filter karne ka SAHI tareeka |

**Chaining insights:**

```python
# Ek hi filter() me multiple kwargs = AND
Post.objects.filter(status='pub', views__gte=100)

# Related field traverse + lookup ek saath — double underscore dono kaam karta hai
Post.objects.filter(author__profile__city__iexact='mumbai')

# __in me queryset — single SQL with subquery (do queries NAHI)
hot_authors = Author.objects.filter(score__gte=90)
Post.objects.filter(author__in=hot_authors)
```

### get() ke exceptions — DoesNotExist & MultipleObjectsReturned

```python
# get() = exactly ONE row ya exception. Dono failure modes handle karna aana chahiye:
try:
    user = User.objects.get(email='a@b.com')
except User.DoesNotExist:               # 0 rows — model-specific exception class hai
    user = None
except User.MultipleObjectsReturned:    # 2+ rows — data integrity bug ka signal!
    user = User.objects.filter(email='a@b.com').order_by('id').first()
    logger.error('Duplicate emails in DB!')   # yeh hona hi nahi chahiye tha — constraint lagao

# Pattern 2: views me — 404 chahiye to boilerplate mat likho
from django.shortcuts import get_object_or_404
user = get_object_or_404(User, email='a@b.com')     # DoesNotExist → Http404

# Pattern 3: "mile to use karo, nahi to None" — first() (exception-free)
user = User.objects.filter(email='a@b.com').first()
```

**Trap:** `except ObjectDoesNotExist` (generic, `django.core.exceptions` se) bhi catch karega — but model-specific `User.DoesNotExist` better hai: nested queries me galat model ka miss silently swallow nahi hoga. `MultipleObjectsReturned` aana = DB me uniqueness constraint missing hai — exception handle karo AUR constraint add karo.

---

## Core Concepts — Part 3: QuerySet Set Operations

```python
qs1 = Post.objects.filter(status='pub').values_list('author_id', 'title')
qs2 = Draft.objects.filter(ready=True).values_list('author_id', 'title')

combined = qs1.union(qs2)              # SQL UNION — duplicates REMOVE (distinct)
combined = qs1.union(qs2, all=True)    # UNION ALL — duplicates rakhega, FASTER
common = qs1.intersection(qs2)         # dono me ho
only_first = qs1.difference(qs2)       # qs1 me ho, qs2 me NA ho
```

### Limitations — yahi interview me poochte hain

```python
u = qs1.union(qs2)
u.filter(author_id=5)     # ❌ NotSupportedError! Union ke BAAD filter() NAHI chal sakta
u.annotate(...)           # ❌ same
u.order_by('title')[:10]  # ✅ sirf order_by + slicing (LIMIT/OFFSET) allowed
```

- **Filter-after-union nahi hota** — DB-level UNION ka result Django ke liye opaque hai. Filter pehle lagao, union baad me.
- Dono querysets ke **columns count + types match** hone chahiye (`values_list` se align karo).
- `union` by default **distinct** karta hai — bade datasets pe costly; duplicates chalte hain to `all=True`.

### Kab union, kab Q-objects ka OR

```python
# SAME model + aage aur filtering chahiye → Q | Q use karo, union NAHI:
Post.objects.filter(Q(status='pub') | Q(author=request.user)).filter(views__gte=10)  # ✅ flexible

# ALAG models / alag tables ka combined result → union hi option hai (Q cross-model nahi chal sakta)
# YA: pehle se distinct/aggregated do queries ko DB-level efficiently jodna ho → union
```

**Rule:** `Q` objects default; `union()` sirf jab (a) different models ko ek result me chahiye, ya (b) dono branches ke apne distinct/annotate pehle ho chuke hon.

---

## Core Concepts — Part 4: Migration Conflicts (team workflow)

### Conflict anatomy

```
main:           0004_add_email ── 0005_add_phone        (teammate ka PR, merged)
tumhara branch: 0004_add_email ── 0005_add_address      (tumne banaya)

git merge ke baad app me DO files: 0005_add_phone.py AUR 0005_add_address.py
→ migration graph me DO LEAF NODES → Django error:
"Conflicting migrations detected; multiple leaf nodes in the migration graph"
```

Migration graph **linear chain** expect karta hai — har migration `dependencies = [('app', '0004_add_email')]` declare karta hai. Do migrations same parent pe = fork = Django ko order nahi pata.

### Fix 1 — `makemigrations --merge` (jab dono independent hon)

```bash
python manage.py makemigrations --merge
# Banata hai: 0006_merge_20260612_1030.py — EMPTY operations, sirf dono leaves pe depend:
#   dependencies = [('blog', '0005_add_phone'), ('blog', '0005_add_address')]
# Graph phir linear: dono 0005 → 0006 merge point
```

Safe **sirf tab** jab dono migrations alag fields/models touch karte hon. Same field dono ne chheda? Merge mat karo — manually resolve.

### Fix 2 — Rebase your migration (cleaner history, recommended jab tumhara abhi merge nahi hua)

```bash
# Apni unapplied migration delete karo, fir se banao — ab woh 0005_add_phone ke upar 0006 banegi
rm blog/migrations/0005_add_address.py
python manage.py migrate blog 0005      # (agar locally apply kar chuke the to pehle: migrate blog 0004, phir delete)
python manage.py makemigrations         # → 0006_add_address, parent 0005_add_phone
```

### Team workflow rules

1. **`makemigrations` se pehle main pull/rebase karo** — conflict banne hi mat do.
2. **Applied (deployed) migration kabhi edit/delete nahi** — sirf unapplied apni wali.
3. Migrations ko **naam do**: `makemigrations -n add_address` — `0005_auto_20260612` se debugging aasaan.
4. CI me `makemigrations --check --dry-run` lagao — model change bina migration ke merge hi na ho.
5. Bade teams: `django-linear-migrations` package — conflict **git merge time** pe hi dikha deta hai (lockfile pattern), deploy pe nahi.

---

## Core Concepts — Part 5: save() Override Pitfalls

```python
class Order(models.Model):
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        self.tax = self.subtotal * Decimal('0.18')    # derived field — save-override ka VALID use
        super().save(*args, **kwargs)                  # super() bhoolna = kuch save hi nahi hoga!
```

### Pitfall 1 — bulk operations save() SKIP karte hain (sabse bada trap)

```python
Order.objects.filter(...).update(subtotal=500)   # ❌ save() NAHI chala — tax stale!
Order.objects.bulk_create([...])                 # ❌ save() skip (signals bhi skip)
Order.objects.bulk_update(orders, ['subtotal'])  # ❌ same
order.save()                                     # ✅ sirf yahi tumhara override chalata hai
```

`update()` direct SQL `UPDATE` hai — Python-level `save()` / signals bypass. Derived-field logic save() me hai to **har bulk path pe woh logic duplicate karna padega** ya bulk ops ban karne padenge. Isliye critical invariants ke liye **DB-level** socho (GeneratedField / trigger / constraint).

### Pitfall 2 — recursion risk

```python
def save(self, *args, **kwargs):
    super().save(*args, **kwargs)
    self.processed = True
    self.save()        # ❌ INFINITE RECURSION — save() khud ko phir bulayega
    # ✅ Fix: pehle hi self.processed set karke EK super().save() karo;
    # post-save me alag update chahiye to: Order.objects.filter(pk=self.pk).update(processed=True)
```

### Pitfall 3 — update_fields respect karo

```python
order.save(update_fields=['status'])    # caller bola sirf status save karo
# Tumhara override tax modify karta hai but update_fields me 'tax' nahi → tax SQL me jayega hi nahi!

def save(self, *args, **kwargs):
    self.tax = self.subtotal * Decimal('0.18')
    if (uf := kwargs.get('update_fields')) is not None:
        kwargs['update_fields'] = set(uf) | {'tax'}    # apna field add karo
    super().save(*args, **kwargs)
```

### Pitfall 4 — signals double-fire

`save()` ke andar do baar `super().save()` (ya save + save pattern) = `pre_save`/`post_save` **do baar** fire. Signal me email bhej rahe ho? Do emails. Save EK baar hi karo.

### Decision framework — save-override vs signal vs service-layer

| Situation | Use | Kyun |
|---|---|---|
| Apne model ka derived field (slug, tax) | `save()` override | Logic data ke paas, har explicit save pe guaranteed |
| Doosri app ke model pe react karna (decoupled) | Signal | Us app ka code modify nahi kar sakte (3rd-party/auth.User) |
| Multi-model business flow (order place → inventory → email) | Service function | Explicit, testable, bulk/Celery se bhi callable |
| Har row pe absolutely guaranteed (bulk bhi) | DB constraint / trigger / GeneratedField | Python layer bypass-proof nahi hai |

---

## Core Concepts — Part 6: Model Validation — clean() / full_clean()

```python
class Booking(models.Model):
    start = models.DateField()
    end = models.DateField()

    def clean(self):
        # Cross-field validation yahan — single-field ke liye validators=[] use karo
        if self.end <= self.start:
            raise ValidationError({'end': 'End date start ke baad honi chahiye'})

# full_clean() = clean_fields() + clean() + validate_unique() + validate_constraints()
```

### KAB auto-call hota hai — yahi classic trap hai

| Path | full_clean() chalta hai? |
|---|---|
| `ModelForm.is_valid()` | ✅ HAAN — sirf yahi auto hai (admin bhi ModelForm hi hai) |
| `obj.save()` | ❌ **NAHI** — invalid data seedha DB me! |
| `objects.create()` / `update()` / `bulk_create()` | ❌ NAHI |
| DRF `ModelSerializer.is_valid()` | ❌ model ka `clean()` NAHI chalta (serializer apna validation karta hai)* |

\* DRF serializer me model-level rule chahiye to `Serializer.validate()` me likho ya explicitly `instance.full_clean()` call karo.

```python
# Non-form paths (shell, scripts, API) pe validation chahiye to KHUD call karo:
booking = Booking(start=s, end=e)
booking.full_clean()     # ValidationError yahan uthega
booking.save()

# Ya save() me force karo (trade-off: har save pe validation cost + bulk paths phir bhi skip):
def save(self, *args, **kwargs):
    self.full_clean()
    super().save(*args, **kwargs)
```

### Constraints vs clean() — dono chahiye, roles alag

| | `clean()` (app-level) | `CheckConstraint`/`UniqueConstraint` (DB-level) |
|---|---|---|
| Kab enforce | Sirf jab koi `full_clean()` call kare | **HAR write pe** — update(), bulk, raw SQL, dusra service bhi |
| Race conditions | ❌ rok nahi sakta (check-then-save gap) | ✅ DB atomically enforce karta hai |
| Expressiveness | Full Python — koi bhi logic, dusre models query | Limited — column expressions |
| Error UX | Friendly per-field messages | IntegrityError (ugly, catch karke translate karo) |

**Rule:** invariant **DB me** (constraint), friendly message **app me** (clean). Django 4.1+ me `validate_constraints()` full_clean ke andar constraints ko bhi pre-check kar leta hai — better UX, but DB constraint hi asli guarantee hai.

---

## Core Concepts — Part 7: Signals vs save() Override — the honest discussion

```python
# signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Order, dispatch_uid='order_create_invoice')
def create_invoice(sender, instance, created, **kwargs):
    if created:
        Invoice.objects.create(order=instance)
```

### Problem 1 — hidden control flow

`Order.objects.create(...)` padhke **pata hi nahi chalta** ki Invoice bhi ban raha hai. 6 mahine baad naya dev "yeh invoice kahan se aaya?" debug karta rehta hai. Signals = action ka effect **codebase me kahin aur** — grep karna padta hai. Service function (`place_order()`) me sab kuch ek jagah visible hota.

### Problem 2 — duplicate registration → dispatch_uid

`ready()` do baar chala (autoreload), ya signals module do paths se import hua → **same handler do baar registered** → invoice DO baar banega. `dispatch_uid='unique-string'` dene se Django duplicate registration ignore karta hai. **Har @receiver pe dispatch_uid lagao — habit bana lo.**

### Problem 3 — bulk ops yahan bhi skip (recap)

`bulk_create()`, `update()`, `bulk_update()` → `pre_save`/`post_save` **fire NAHI hote** (`.delete()` queryset wala `pre_delete/post_delete` fire karta hai, per-object). Signal-based critical logic + bulk ops = silent data gaps.

### Decision table

| Criteria | save() override | Signal | Service layer |
|---|---|---|---|
| Visibility/debuggability | Medium (model me hai) | ❌ Worst (kahin aur hai) | ✅ Best (ek function me sab) |
| Decoupling (3rd-party model pe react) | ❌ possible nahi | ✅ only option | ❌ unka code call nahi karta tumhe |
| Bulk-ops safe | ❌ | ❌ | ✅ (service hi bulk handle kare) |
| Testability | Medium | Hard (implicit firing) | ✅ plain function |

**Modern consensus (HackSoft styleguide, Two Scoops):** apne code ke beech communication ke liye signals **mat** use karo — service layer use karo. Signals sirf jab sender ka code tumhara nahi hai (`post_save` on `User`, `post_migrate`, etc.).

---

## Core Concepts — Part 8: Django Cache Framework Specifics

### 3 levels — per-view, fragment, low-level

```python
# 1. PER-VIEW — cache_page (poora response cache, URL+Vary headers ke basis pe)
from django.views.decorators.cache import cache_page

@cache_page(60 * 15)                  # 15 min
def product_list(request): ...

path('products/', cache_page(900)(views.product_list)),   # URLconf me bhi laga sakte ho

# TRAP: per-USER content cache_page me mat daalo — pehle user ka page SABKO milega.
# Sirf GET/HEAD + status 200 cache hota hai. Har query-string = alag cache entry.
```

```html
<!-- 2. TEMPLATE FRAGMENT — page ka sirf expensive hissa -->
{% load cache %}
{% cache 300 sidebar request.user.username %}   <!-- extra args = cache key ka part -->
    ... expensive sidebar queries ...
{% endcache %}
<!-- per-user variation extra args se handle hoti hai — yahi fragment ka advantage hai -->
```

```python
# 3. LOW-LEVEL — full control
from django.core.cache import cache

cache.set('hot_posts', posts, timeout=300)
posts = cache.get('hot_posts')                       # miss pe None
posts = cache.get_or_set('hot_posts', compute_hot_posts, 300)   # callable LAZY — sirf miss pe chalta hai
cache.delete('hot_posts')
cache.incr('page_hits')                              # atomic increment (Redis/memcached pe)
```

### django `cached_property` vs `functools.cached_property` — difference!

```python
from django.utils.functional import cached_property      # Django wala
from functools import cached_property                    # stdlib wala

class Report(models.Model):
    @cached_property
    def expensive_total(self):
        return self.lines.aggregate(t=Sum('amount'))['t']   # pehli access pe compute,
                                                            # phir instance.__dict__ me cache

r.expensive_total      # query chali
r.expensive_total      # cache se — NO query
del r.expensive_total  # invalidate (DONO versions me yahi tareeka)
```

**Difference (interview-grade):** Python 3.8–3.11 ke `functools.cached_property` me **class-level lock** tha — multithreaded code me us property ki **saari instances** ek lock pe serialize ho jaati thin (major perf bug; 3.12 me lock hata diya). Django wale me **kabhi lock tha hi nahi** — lightweight, isliye Django internally apna use karta hai. Dono instance `__dict__` me cache karte hain → instance ki lifetime tak hi valid (request-scoped models pe perfect). 3.12+ pe dono practically same hain.

### Invalidation patterns + version keys

```python
# Pattern 1: write pe explicit delete (simple, par har write-path yaad rakhna padta hai)
def save(self, *args, **kwargs):
    super().save(*args, **kwargs)
    cache.delete(f'product:{self.pk}')

# Pattern 2: VERSION KEY — group invalidation bina sab keys jaane
v = cache.get_or_set('products:version', 1, None)
cache.set(f'products:v{v}:list:page1', data, 600)
# Invalidate ALL product caches ek incr se — purani keys orphan hoke TTL pe mar jaayengi:
cache.incr('products:version')

# Pattern 3: Django built-in version param (same idea, framework-level)
cache.set('list', data, version=2); cache.get('list', version=2)

# Pattern 4: TTL hi kaafi hai — "5 min stale chalega" wale data pe invalidation likho hi mat
```

---

## Core Concepts — Part 9: TestCase vs TransactionTestCase

### Core difference — rollback vs real commits

```python
from django.test import TestCase, TransactionTestCase

class FastTests(TestCase):
    # HAR test ATOMIC block me wrap hota hai → end pe ROLLBACK. DB kabhi commit dekhta hi nahi.
    # FAST (rollback >> truncate). 95% tests ke liye yahi.
    ...

class RealCommitTests(TransactionTestCase):
    # REAL commits hote hain; har test ke baad saari tables FLUSH (truncate) → SLOW.
    # Chahiye jab: transaction behavior khud test karna ho, on_commit, threads/concurrency.
    ...
```

### `on_commit` TestCase me FIRE NAHI hota — captureOnCommitCallbacks fix

```python
# Production code:
def place_order(...):
    order = Order.objects.create(...)
    transaction.on_commit(lambda: send_confirmation_email.delay(order.pk))   # commit ke baad hi

class OrderTests(TestCase):
    def test_email_queued(self):
        place_order(...)
        # ❌ Email task enqueue NAHI hua — TestCase me commit hota hi nahi, callback pending hi reh gaya!

        # ✅ FIX — Django 3.2+:
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            place_order(...)
        self.assertEqual(len(callbacks), 1)     # callbacks execute bhi hue (execute=True)
```

Alternative: us ek test ko `TransactionTestCase` bana do (slow) — but `captureOnCommitCallbacks` better hai: fast TestCase + callbacks bhi verified.

### setUpTestData vs setUp

```python
class PostTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # CLASS-LEVEL, poori class me EK BAAR — class-wide atomic me banta hai,
        # har test ke baad rollback se wapas isi state pe. Read-only fixtures yahan = HUGE speedup.
        cls.author = User.objects.create_user('ashish')
        cls.posts = [Post.objects.create(author=cls.author, title=f'P{i}') for i in range(50)]

    def setUp(self):
        # HAR TEST se pehle — sirf woh cheezein jo test MUTATE karta hai ya per-test fresh chahiye
        self.client.force_login(self.author)
```

50 posts × 20 tests: `setUp` me banao to 1000 INSERTs, `setUpTestData` me 50. **Trap:** `setUpTestData` ke objects in-memory state tests ke beech leak na ho isliye Django har test me unhe deepcopy-style refresh karta hai (3.2+) — DB-modify kiya to rollback se theek ho jaata hai, but in-place python mutation se savdhan.

### pytest-django marks

```python
import pytest

@pytest.mark.django_db                      # TestCase jaisa — atomic + rollback
def test_create_post(): ...

@pytest.mark.django_db(transaction=True)    # TransactionTestCase jaisa — real commits (on_commit chalega)
def test_on_commit_hook(): ...

@pytest.fixture
def author(db):                              # 'db' fixture = django_db mark ka fixture-form
    return User.objects.create_user('ashish')
```

---

## Core Concepts — Part 10: Auth Functions Internals

```python
from django.contrib.auth import authenticate, login, logout

def login_view(request):
    user = authenticate(request, username=u, password=p)   # credentials → User ya None
    if user is not None:
        login(request, user)                               # session me user bind
        return redirect('home')
```

**`authenticate()` internally:** `AUTHENTICATION_BACKENDS` list pe loop — har backend ka `.authenticate(request, **creds)` call. Pehla non-None User jeeta; backend `PermissionDenied` raise kare to chain wahi ruk jaati hai. Default `ModelBackend`: username se user fetch → `check_password()` → `user_can_authenticate()` (is_active check). Subtle detail: user **na bhi mile** to bhi password hasher ek baar chalata hai — timing attack se username enumeration na ho.

**`login()` internally:** session me 3 cheezein likhta hai — `_auth_user_id` (pk), `_auth_user_backend` (kaunse backend se aaya), `_auth_user_hash` (password hash ka HMAC — password change hote hi BAAKI sessions invalid!). Aur **session key ROTATE karta hai** (`cycle_key`) — yahi **session fixation attack** rokta hai: attacker tumhe apni known session-id de, tum login karo, attacker wahi id use kare — rotation se login ke baad id nayi hai, attacker ke paas purani bekaar.

**`logout()` internally:** `request.session.flush()` — session data delete + DB/store row delete + **nayi empty session key**. Sirf "user ko None set karna" nahi — poora session destroy, taaki session reuse na ho.

```python
# Protection — FBV vs CBV:
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin

@login_required                                   # FBV — anonymous → settings.LOGIN_URL + ?next=/current/
def dashboard(request): ...

class Dashboard(LoginRequiredMixin, TemplateView):  # CBV — mixin LEFTMOST (MRO, file 37 dekho)
    template_name = 'dash.html'
    # login_url / redirect_field_name override kar sakte ho; raise_exception=True → 403 instead of redirect
```

Same kaam, do form factors — `@login_required` class pe directly **nahi** lagta (function decorator hai); CBV pe mixin ya `@method_decorator(login_required, name='dispatch')`.

---

## Core Concepts — Part 11: Deployment Gaps — WhiteNoise + DEBUG=False Checklist

### WhiteNoise — Django se hi static serve karo (nginx config ke bina)

```bash
pip install whitenoise
```

```python
# settings.py
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',     # ← SecurityMiddleware ke turant BAAD, sabse upar warna
    # ... baaki sab
]

STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {                                          # Django 4.2+ style
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
# Manifest storage = filename me content-hash (style.a1b2c3.css) → cache-bust FREE,
# far-future Cache-Control headers + gzip/brotli pre-compression bhi free
```

```bash
python manage.py collectstatic --noinput    # deploy step — sab static STATIC_ROOT me
```

**Kyun zaroori:** `DEBUG=False` pe Django/runserver static files **serve hi nahi karta** — "CSS gayab ho gaya prod me" wali classic problem. WhiteNoise WSGI-level pe efficiently serve karta hai — chhote/medium apps ke liye nginx/CDN se pehle ka pragmatic default (Heroku/Railway/Render pattern).

### DEBUG=False checklist

```python
DEBUG = False
ALLOWED_HOSTS = ['api.mysite.com']        # empty + DEBUG=False = har request pe 400 Bad Request!
CSRF_TRUSTED_ORIGINS = ['https://mysite.com']   # cross-origin POST forms ke liye (Django 4+ scheme zaroori)

# SECURE_* settings — `manage.py check --deploy` yeh sab audit karta hai:
SECURE_SSL_REDIRECT = True                # http → https redirect
SECURE_HSTS_SECONDS = 31536000            # browser ko bolo: sirf https (pehle chhote value se test karo!)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True              # cookies sirf https pe jaayein
CSRF_COOKIE_SECURE = True
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']   # hard-coded NAHI — env se, missing pe crash hi sahi hai
```

| Checklist item | Bhoole to kya hota hai |
|---|---|
| `ALLOWED_HOSTS` set | Har request 400 — Host-header attack protection trigger |
| `collectstatic` + WhiteNoise/nginx | CSS/JS 404 — DEBUG=False me Django serve nahi karta |
| `templates/404.html`, `templates/500.html` | Users ko ugly plain-text error pages (debug traceback to milta hi nahi — woh sirf DEBUG=True) |
| `SECURE_*` settings | Cookies http pe leak, no HSTS — `check --deploy` chalao |
| Error tracking (Sentry) | 500s silently — DEBUG=False pe traceback sirf logs/ADMINS email me |

---

## Interview Q&A

**Q1:** Middleware ke 5 hooks aur unka order?
**A:** `__init__` (server start, ek baar), `__call__` pre-get_response part (request phase, **top-down** MIDDLEWARE order me), `process_view` (URL resolve ke baad, view se pehle, top-down), `process_exception` (view uncaught exception pe, **bottom-up**), `process_template_response` (sirf TemplateResponse pe, render se pehle, bottom-up), `__call__` post part (response phase, bottom-up). Mental model: onion — request andar, response bahar.

**Q2:** Sentry har exception kaise pakadta hai?
**A:** `process_exception` hook — view ka uncaught exception Django middleware chain me bottom-up propagate karta hai, Sentry ka middleware/integration wahan capture karke None return karta hai taaki Django ka normal 500 handling bhi chale. Isliye zero view-code change me full error tracking milti hai.

**Q3:** Middleware short-circuit kare to kya hota hai?
**A:** Jis middleware ne `get_response()` call kiye bina HttpResponse return kiya — uske NEECHE wale saare middleware + view skip. Lekin uske UPAR wale (jo request phase pass kar chuke) ka response phase chalega. Isliye SecurityMiddleware top pe hota hai — har response, short-circuited bhi, security headers paaye.

**Q4:** `get()` kaunse exceptions raise karta hai, kaise handle karoge?
**A:** 0 rows → `Model.DoesNotExist`, 2+ rows → `Model.MultipleObjectsReturned`. Patterns: try/except model-specific class se; views me `get_object_or_404`; "None chalega" semantics pe `.filter().first()`. `MultipleObjectsReturned` aana matlab uniqueness constraint missing — handle bhi karo, constraint bhi lagao.

**Q5:** `union()` ke baad `filter()` kyun nahi chalta? Alternative?
**A:** SQL UNION ka result combined opaque set hai — Django uspe sirf `order_by`/slicing (LIMIT/OFFSET) support karta hai; filter/annotate `NotSupportedError` dete hain. Same model pe OR + aage filtering chahiye to `Q(a) | Q(b)` use karo. `union()` tab jab alag models/tables ka combined result chahiye ya branches pehle se distinct/annotated hain.

**Q6:** Do branches ne same number ki migration banayi — kya hota hai, kaise fix?
**A:** Migration graph me do leaf nodes → "Conflicting migrations detected". Fix: independent changes hon to `makemigrations --merge` (empty merge migration dono pe depend karti hai); cleaner: apni unapplied migration delete karke dobara `makemigrations` (ab woh teammate wali ke upar banegi). Rules: makemigrations se pehle main pull, applied migrations kabhi edit nahi, CI me `makemigrations --check`.

**Q7:** `save()` override kiya, phir bhi field update nahi hua — kaise?
**A:** `update()`, `bulk_create()`, `bulk_update()` direct SQL hain — `save()` aur signals dono skip. Aur agar caller `save(update_fields=['x'])` de aur override ne 'y' modify kiya but update_fields me add nahi kiya to 'y' SQL me jayega hi nahi. Bypass-proof invariant chahiye to DB level pe jao (constraint/GeneratedField/trigger).

**Q8:** `clean()` likha tha, invalid data phir bhi save ho gaya — kyun?
**A:** `save()` **kabhi** `full_clean()` call nahi karta — auto-validation sirf `ModelForm.is_valid()` (admin included) me hoti hai. `create()`, `bulk_create()`, DRF ModelSerializer bhi model `clean()` nahi chalate. Fix: non-form paths pe khud `full_clean()` call karo, aur asli invariants DB constraints me rakho — woh race conditions me bhi enforce hote hain, clean() nahi.

**Q9:** TestCase me `transaction.on_commit` ka callback kyun nahi chalta? Fix?
**A:** TestCase har test ko atomic me wrap karke ROLLBACK karta hai — commit hota hi nahi, to on_commit callbacks pending hi reh jaate hain. Fix: `with self.captureOnCommitCallbacks(execute=True) as cb:` — callbacks capture + execute, TestCase ki speed bhi bani rahti hai. Alternative `TransactionTestCase` (ya pytest me `django_db(transaction=True)`) real commits karta hai but har test ke baad table flush = slow.

**Q10:** `login()` session key rotate kyun karta hai?
**A:** Session fixation attack rokne ke liye — attacker victim ko apni known session-id de deta hai (URL/cookie injection se); victim login kare aur id same rahe to attacker wahi id se logged-in session use kar lega. `login()` `cycle_key()` se nayi session key banata hai, saath me `_auth_user_hash` (password ka HMAC) store karta hai jisse password change hote hi baaki sessions invalid ho jaate hain. `logout()` poora `session.flush()` karta hai.

---

## References

- [Middleware](https://docs.djangoproject.com/en/5.0/topics/http/middleware/) — hooks + ordering
- [QuerySet API — lookups, union](https://docs.djangoproject.com/en/5.0/ref/models/querysets/)
- [Migrations — version control](https://docs.djangoproject.com/en/5.0/topics/migrations/#version-control)
- [Model validation (full_clean)](https://docs.djangoproject.com/en/5.0/ref/models/instances/#validating-objects)
- [Signals](https://docs.djangoproject.com/en/5.0/topics/signals/) + HackSoft styleguide (signals kab NAHI)
- [Cache framework](https://docs.djangoproject.com/en/5.0/topics/cache/)
- [Testing tools — TestCase, captureOnCommitCallbacks](https://docs.djangoproject.com/en/5.0/topics/testing/tools/)
- [WhiteNoise docs](https://whitenoise.readthedocs.io/) + `manage.py check --deploy`
