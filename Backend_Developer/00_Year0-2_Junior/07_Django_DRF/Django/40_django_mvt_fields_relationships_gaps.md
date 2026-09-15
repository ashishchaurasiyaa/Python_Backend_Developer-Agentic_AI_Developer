# Django MVT, Fields & Relationships Gaps — Architecture, startproject/startapp, null vs blank, on_delete, Request/Response, Static/Media

## Why It Matters

Framework audit Round-2 me yeh gaps confirm hue — sab "Day 1 basics" lagte hain, but inka **deep version** hi junior aur mid-level me farak karta hai:

- "Django MVC hai ya MVT? View kya hota hai?" → 80% candidates yahin confuse ho jaate hain (Django ka view = MVC ka controller!)
- "`null=True` aur `blank=True` me kya difference?" → THE classic screening question — DB-level vs validation-level
- "`on_delete=PROTECT` vs `RESTRICT`?" → 5% log hi difference bata paate hain
- "`JsonResponse` me list bhejne pe error kyun aaya?" → `safe=False` trap
- "Production me static files kaun serve karta hai? runserver kyun nahi?" → deployment maturity check

Yeh file un sab basics ko production-depth pe le jaati hai jo "easy" samajh ke skip ho jaate hain.

---

## Core Concepts — Part 1: MVT Architecture DEEP

### Request ka full journey — flow diagram

```
Browser request: GET /articles/5/
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│  WSGI/ASGI server (gunicorn/uvicorn)                    │
│        │                                                │
│        ▼                                                │
│  Middleware stack (top→bottom request, bottom→top resp) │
│        │                                                │
│        ▼                                                │
│  URLconf (urls.py) ──── path('articles/<int:pk>/')      │
│        │  matched! kwargs={'pk': 5}                     │
│        ▼                                                │
│  VIEW (views.py) ◄──── yahi traffic controller hai      │
│        │                                                │
│        ├──► MODEL (models.py) ──► ORM ──► Database      │
│        │         Article.objects.get(pk=5)              │
│        │                                                │
│        ├──► TEMPLATE (article_detail.html)              │
│        │         context = {'article': article}         │
│        │         render() = template + context → HTML   │
│        ▼                                                │
│  HttpResponse (HTML/JSON/file...)                       │
└─────────────────────────────────────────────────────────┘
        │
        ▼
Browser ko response
```

**Har layer ka kaam:**
- **Model** — data structure + business data access. "Article kya hai, kahan stored hai, kaise fetch hota hai."
- **View** — request aata hai, decide karta hai kya karna hai: model se data lo, template chuno, response banao. **Logic ka glue.**
- **Template** — presentation only. HTML me placeholders, loops, conditions — but business logic NAHI.

### MVC se mapping — THE classic confusion

| MVC (general) | Django (MVT) | Kaam |
|---|---|---|
| Model | **Model** | Data + business rules — same naam, same kaam |
| **Controller** | **View** (views.py!) | Request handle karo, decide karo kya hoga |
| **View** | **Template** | User ko kya DIKHTA hai — presentation |
| (Controller ka routing part) | URLconf + framework itself | Request ko sahi handler tak pahunchana |

**Yahi trap hai:** MVC ka "view" = jo user dekhta hai (UI). Django ka "view" = jo request process karta hai (MVC me yeh controller hota!). Interview me confidently bolo: **"Django ka view function MVC ke controller ka role play karta hai, aur Django ka template MVC ke view ka."**

**Kyun Django ne MTV bola?** Django docs ki official line: unke hisaab se "view" ka matlab hai "**which data you see**, not how you see it" — view = data ka description (kaunsa data present hoga), template = kaise present hoga. Aur "controller" unke liye framework khud hai — jo machinery URL se function tak request pahunchati hai. Naming philosophy ka difference hai, architecture practically MVC-family ka hi hai. Isliye Django ko log "MTV framework" bhi kehte hain — Model-Template-View.

```python
# Ek hi flow teeno layers me — minimal but complete:

# models.py (M)
class Article(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()

# views.py (V — but actually controller!)
def article_detail(request, pk):
    article = get_object_or_404(Article, pk=pk)        # Model se data
    return render(request, 'blog/detail.html', {'article': article})  # Template ko de do

# detail.html (T — actual "view" in MVC sense)
# <h1>{{ article.title }}</h1>  <p>{{ article.body }}</p>
```

---

## Core Concepts — Part 2: startproject vs startapp

```bash
django-admin startproject mysite .     # PROJECT — poori website ka container
python manage.py startapp blog        # APP — ek feature/domain ka module
```

### Kya generate hota hai

```
mysite/                          blog/
├── manage.py                    ├── migrations/
└── mysite/                      │   └── __init__.py
    ├── __init__.py              ├── __init__.py
    ├── settings.py   ← config   ├── admin.py       ← admin registration
    ├── urls.py       ← root URLconf  ├── apps.py    ← AppConfig (app ki identity)
    ├── asgi.py       ← async entry   ├── models.py
    └── wsgi.py       ← sync entry    ├── tests.py
                                 └── views.py
                                 # (urls.py khud banana padta hai — convention)
```

**Philosophy:** project = configuration + glue (settings, root urls, deployment entrypoints). App = **reusable, self-contained feature** — `blog`, `payments`, `accounts`. Ek project me kai apps; ek achhi app kisi DOOSRE project me bhi drop ho sake (pip-installable Django packages — `django.contrib.admin`, `rest_framework` — sab "apps" hi hain). Rule of thumb: "Could I describe this app in one sentence?" — `orders` haan, `utils_and_everything` nahi.

### INSTALLED_APPS registration — actually kya karta hai

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    ...
    'blog',                    # ya explicit: 'blog.apps.BlogConfig'
]
```

Register karne se Django app ke liye yeh sab **activate** karta hai:

1. **App loading** — `apps.py` ka `AppConfig.ready()` hook chalta hai (signals connect karne ki standard jagah).
2. **Models discovery** — `blog/models.py` ke models app registry me aate hain. Bina iske: `RuntimeError: Model class ... doesn't declare an explicit app_label and isn't in an application in INSTALLED_APPS`.
3. **Migrations** — `makemigrations`/`migrate` sirf registered apps ki migrations dekhte hain.
4. **Templates namespacing** — `APP_DIRS=True` ke saath Django har registered app ke `templates/` folder me dhundhta hai. Convention: `blog/templates/blog/detail.html` (double folder!) — taaki do apps ke `detail.html` clash na karein.
5. **Static namespacing** — same pattern: `blog/static/blog/style.css`, `collectstatic` registered apps ke static folders sweep karta hai.
6. **Admin/management commands/tests discovery** — `admin.py` autoload, `blog/management/commands/` ke commands available, test runner app ke tests uthata hai.

**Trap:** app banayi, models likhe, `makemigrations` bola "No changes detected" — 90% baar INSTALLED_APPS me add karna bhool gaye ho.

---

## Core Concepts — Part 3: Model Fields DEEP

### Common field types — overview table

| Field | DB type (Postgres) | Notes |
|---|---|---|
| `CharField(max_length=N)` | `varchar(N)` | max_length REQUIRED |
| `TextField()` | `text` | unbounded; forms me textarea |
| `IntegerField` / `BigIntegerField` | `integer` / `bigint` | |
| `DecimalField(max_digits, decimal_places)` | `numeric` | **paison ke liye yahi** — FloatField kabhi nahi (binary rounding!) |
| `BooleanField` | `boolean` | default do, warna migration prompt |
| `DateTimeField(auto_now_add=)` / `(auto_now=)` | `timestamptz` | created_at / updated_at pattern |
| `EmailField` / `URLField` / `SlugField` | `varchar` | = CharField + validator (DB me koi farak nahi!) |
| `UUIDField` | `uuid` | PK ke liye: `default=uuid.uuid4` |
| `JSONField` | `jsonb` | sab supported DBs pe (Django 3.1+) |
| `FileField` / `ImageField` | `varchar` (path!) | file DISK/S3 pe, DB me sirf path string |
| `ForeignKey` / `OneToOneField` / `ManyToManyField` | FK column / FK+unique / junction table | Part 4 me deep |

### null vs blank — THE classic

| | `null=True` | `blank=True` |
|---|---|---|
| Layer | **Database** — column `NULL` allow karega | **Validation** — forms/serializers/`full_clean()` empty allow karenge |
| Kis pe effect | Schema (migration banegi) | Sirf Python-level validation |
| Default | `False` (NOT NULL) | `False` (required) |

```python
class Profile(models.Model):
    # Dono chahiye optional text ke liye? NAHI — sirf blank!
    bio = models.CharField(max_length=500, blank=True)              # ✅ empty string '' store hogi
    # null=True CharField pe ❌ — kyun? Niche dekho.

    # Date/number/FK optional ho to DONO chahiye:
    birth_date = models.DateField(null=True, blank=True)            # ✅
    manager = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
```

**CharField me `null=True` kyun avoid?** String fields me "no data" ke **do representations** ban jaate hain — `NULL` aur `''` (empty string). Ab queries me dono check karo (`Q(bio='') | Q(bio__isnull=True)`), uniqueness weird (`unique=True` + multiple NULLs allowed!), bugs ka factory. Django convention: **string fields me empty = `''`, null kabhi nahi** (exception: `unique=True` + optional — tab null=True justified hai taaki multiple empty values unique constraint na todein). Non-string fields (Date, Integer, FK) me empty string possible hi nahi — wahan `null=True` hi ek raasta hai.

**Combos yaad rakho:** `blank=True` alone = form me optional, DB me `''` (strings). `null=True` alone = DB allow karega but form bolega "required" — bekaar combo, almost hamesha galti.

### choices — 3 styles

```python
# Style 1: tuples ka list (legacy, ab bhi common)
STATUS_CHOICES = [
    ('draft', 'Draft'),          # (DB-stored value, human-readable label)
    ('published', 'Published'),
]
status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

# Style 2: TextChoices (Django 3.0+ — PREFERRED) — enum jaisa, namespaced, type-safe
class Article(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'             # value, label
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

# Usage — magic strings GAYAB:
Article.objects.filter(status=Article.Status.PUBLISHED)   # ✅ typo = AttributeError turant
Article.objects.filter(status='publishd')                 # ❌ typo silently 0 results!

# Style 3: IntegerChoices — jab DB me int store karna ho (chhota, fast comparisons)
class Priority(models.IntegerChoices):
    LOW = 1, 'Low'
    HIGH = 2, 'High'
priority = models.IntegerField(choices=Priority.choices, default=Priority.LOW)

# get_FOO_display() — stored value se label (FREE method har choices field pe):
a = Article(status='draft')
a.status                     # 'draft'         ← DB value
a.get_status_display()       # 'Draft'         ← human label, templates me use karo
# Template: {{ article.get_status_display }}
```

**Note:** choices **app-level validation** hai (forms/full_clean) — DB me CHECK constraint NAHI banta. Raw SQL ya `.save()` (bina full_clean) se invalid value ghus sakti hai. Hard guarantee chahiye to `CheckConstraint(condition=Q(status__in=[...]))` lagao (file 38).

### default pitfalls

```python
# ❌ TRAP 1: mutable default — Python ka classic, Django me bhi
tags = models.JSONField(default=[])      # ❌ SAB instances SAME list share karenge!
# (+ makemigrations warning: W039) — ek instance me append → sab me dikhega (pre-save)

# ✅ Callable do — har instance ko FRESH object milega
tags = models.JSONField(default=list)    # ✅ list (callable), list() NAHI, [] NAHI
meta = models.JSONField(default=dict)    # ✅ dict — yaad rakho: default={} bhi ❌

# ❌ TRAP 2: default=timezone.now() vs default=timezone.now
created = models.DateTimeField(default=timezone.now())   # ❌ () laga diya —
# import time pe EK BAAR evaluate hua — server start ka time SAB rows me!
created = models.DateTimeField(default=timezone.now)     # ✅ callable — har INSERT pe fresh

# default vs db_default (Django 5.0+)
class Order(models.Model):
    status = models.CharField(max_length=20, default='pending')        # Python-level
    created = models.DateTimeField(db_default=Now())                   # DB-level DEFAULT clause!
```

| | `default=` | `db_default=` (5.0+) |
|---|---|---|
| Kahan apply | Python me, instance creation pe | DB schema me `DEFAULT` clause |
| Raw SQL INSERT pe | ❌ apply nahi hota | ✅ DB khud bharta hai |
| Doosri app/service same DB pe | ❌ unko nahi milta | ✅ milta hai |
| Callable (`timezone.now`) | ✅ Python callable | DB functions (`Now()`, literals) |
| Use kab | App-only writes, dynamic Python logic | Multi-writer DB, DB-level guarantee chahiye |

---

## Core Concepts — Part 4: Relationships DEEP

### on_delete — ALL options semantics

`User` delete ho raha hai, uske `Order`s ka kya hoga? — yahi on_delete decide karta hai. **Important: yeh (mostly) Django/Python-level enforce hota hai, DB-level ON DELETE nahi** — Django collector related objects dhundh ke Python me action leta hai (isliye signals fire hote hain CASCADE me).

| Option | Kya hota hai | Kab use |
|---|---|---|
| `CASCADE` | Children bhi delete | Owned data — user ke sessions, comments |
| `PROTECT` | `ProtectedError` raise — delete **rok do** | Critical refs — Invoice→Customer (paid invoice wale customer ko delete mat hone do) |
| `RESTRICT` (3.1+) | `RestrictedError` — but **CASCADE-through allowed** (niche) | PROTECT ka nuanced bhai |
| `SET_NULL` | FK column NULL (needs `null=True`) | History rakho, link todo — Comment→deleted User = "anonymous" |
| `SET_DEFAULT` | FK ko `default=` value (needs default) | Fallback owner — "deleted_user" sentinel |
| `SET(value_or_callable)` | Custom value/callable se replace | `SET(get_sentinel_user)` — lazy sentinel fetch |
| `DO_NOTHING` | Kuch nahi — **IntegrityError aayega** (DB FK violation) jab tak DB-level handling na ho | Tab hi jab DB me khud `ON DELETE` trigger/rule lagaya ho |

**PROTECT vs RESTRICT — the difference (interview gold):**

```python
class Artist(models.Model): ...
class Album(models.Model):
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE)
class Song(models.Model):
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE)
    album = models.ForeignKey(Album, on_delete=models.RESTRICT)   # ← yahan dekho

song_artist.delete()
# PROTECT hota to: ❌ ProtectedError — Song exists, full stop. Koi sawal nahi.
# RESTRICT hai to: ✅ ALLOWED! Kyunki Album bhi USI artist.delete() cascade me
#   delete ho raha hai — Song apne album ke SAATH ja raha hai, orphan nahi ban raha.
# RESTRICT sirf tab rokta hai jab Song bachta but uska Album udd jaata —
# i.e. "direct delete of referenced object" blocked, "same-operation cascade" allowed.
album.delete()    # ❌ RestrictedError — Song reference karta hai, Album akela delete nahi hoga
```

**One-liner:** PROTECT = unconditional block. RESTRICT = block, **except** jab referenced object usi cascade me waise bhi delete ho raha ho.

**DB-level note:** Django migrations FK pe DB me `ON DELETE` clause generally NAHI lagati (deferrable constraint hoti hai) — cascade Python me hota hai. Matlab: raw SQL `DELETE FROM users` pe Django ka CASCADE/SET_NULL **nahi chalega** — IntegrityError ya orphans. Multi-writer DBs me DB-level FK actions raw migration se lagao agar zaroori ho.

### M2M with through= — junction me extra fields

```python
class Person(models.Model):
    name = models.CharField(max_length=100)

class Group(models.Model):
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(Person, through='Membership', related_name='groups')

class Membership(models.Model):              # junction table AB TUMHARA model hai
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    date_joined = models.DateField(auto_now_add=True)      # ← extra fields — yahi point hai!
    role = models.CharField(max_length=50, default='member')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['person', 'group'], name='uniq_membership')]

# Add karna — through_defaults se extra fields bharo (Django 2.2+ .add() bhi chalta hai):
group.members.add(person, through_defaults={'role': 'admin'})
# Ya explicitly: Membership.objects.create(person=p, group=g, role='admin')

# Query — dono direction normal M2M jaisa + junction directly queryable:
group.members.all()                                   # Person queryset
person.groups.filter(membership__role='admin')        # through fields se filter!
Membership.objects.filter(group=g).select_related('person')   # roster with roles
```

**Kab explicit through?** Jab relationship KHUD me data ho — join date, role, quantity (OrderItem!), expiry. Plain M2M = sirf "linked hai/nahi". Pro tip: shuru se hi `through` socho agar thoda bhi doubt ho — baad me plain M2M → through migration painful hai (table rename dance).

### related_name vs related_query_name

```python
class Article(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='articles',            # reverse ACCESSOR — instance se
        related_query_name='article',       # reverse FILTER name — queryset lookups me
    )

user.articles.all()                          # ← related_name (manager on instance)
User.objects.filter(article__title='X')      # ← related_query_name (filter path)

# Defaults samjho:
# related_name nahi diya       → accessor: article_set (modelname_set)
# related_query_name nahi diya → related_name use hota (ya model name agar wo bhi nahi)
# Isliye sirf related_name='articles' diya to filter bhi 'articles__title' hoga —
# plural filter path thoda awkward padhta hai: filter(articles__title=...) —
# related_query_name='article' dene se filter singular: filter(article__title=...) — readable.
```

| | `related_name` | `related_query_name` |
|---|---|---|
| Kahan use | `user.articles.all()` — instance accessor | `User.objects.filter(article__...)` — lookup path |
| Default | `<model>_set` | `related_name` ki value (ya model name) |
| `'+'` special | `related_name='+'` = reverse accessor **disable** | — |

### Self-referencing FK + symmetrical M2M

```python
class Employee(models.Model):
    name = models.CharField(max_length=100)
    manager = models.ForeignKey(
        'self',                              # ← string 'self' — apne aap ko point
        null=True, blank=True,               # CEO ka koi manager nahi
        on_delete=models.SET_NULL,
        related_name='reports',              # manager.reports.all() = direct reports
    )

emp.manager           # upar
emp.reports.all()     # niche — org tree dono direction

class Person(models.Model):
    # Symmetrical (default for self-M2M): friendship — A friend of B ⇒ B friend of A
    friends = models.ManyToManyField('self')                      # symmetrical=True default
    # a.friends.add(b) → b.friends me a AUTOMATICALLY (ek hi row, dono direction implied)
    # NOTE: symmetrical M2M me related_name ALLOWED NAHI (reverse = same accessor)

    # Asymmetric: Twitter-follow — A follows B ≠ B follows A
    following = models.ManyToManyField(
        'self', symmetrical=False, related_name='followers',
    )
    # a.following.add(b) → b.followers me a, but b.following me a NAHI
```

---

## Core Concepts — Part 5: HttpRequest / HttpResponse

### HttpRequest — kya kya milta hai

```python
def my_view(request):
    request.method            # 'GET' / 'POST' ...
    request.GET               # QueryDict — URL query params: /search?q=django → request.GET['q']
    request.GET.get('q', '')  # ✅ .get() with default — ['q'] KeyError de sakta hai
    request.GET.getlist('tag')# ?tag=a&tag=b → ['a','b'] — multi-value ke liye getlist!

    request.POST              # QueryDict — SIRF form-encoded body (multipart/urlencoded)
    request.body              # raw bytes — JSON API me yahi: json.loads(request.body)
    # TRAP: JSON request me request.POST EMPTY hota hai! JSON form-data nahi hai.

    request.FILES             # uploaded files (multipart POST me) — request.FILES['avatar']
    request.META              # WSGI environ dict — 'REMOTE_ADDR', 'HTTP_USER_AGENT', ...
    request.headers           # (2.2+) friendly, case-insensitive: request.headers['User-Agent']
                              # ✅ headers use karo, META['HTTP_X_FOO'] ka mangled form nahi
    request.user              # AuthenticationMiddleware se — User ya AnonymousUser
    request.path              # '/articles/5/'
```

### HttpResponse subclasses table

| Class | Status | Use |
|---|---|---|
| `HttpResponse('hi')` | 200 | Base — content + content_type |
| `JsonResponse({'k': 1})` | 200 | dict → JSON + `Content-Type: application/json` |
| `HttpResponseRedirect('/x/')` | 302 | Temporary redirect (shortcut: `redirect()`) |
| `HttpResponsePermanentRedirect` | 301 | Permanent — browser CACHE karta hai! |
| `HttpResponseNotFound` | 404 | (mostly `raise Http404` / `get_object_or_404` better) |
| `HttpResponseForbidden` | 403 | Permission denied |
| `HttpResponseNotAllowed(['GET'])` | 405 | Method not allowed |
| `HttpResponseBadRequest` | 400 | Malformed request |
| `FileResponse(open(f,'rb'))` | 200 | Streaming file download (binary mode kholo!) |
| `StreamingHttpResponse(gen)` | 200 | Generator se chunks — bade CSV exports |

### JsonResponse — safe=False trap

```python
return JsonResponse({'users': [...]})         # ✅ dict — default
return JsonResponse([1, 2, 3])                # ❌ TypeError: In order to allow non-dict
                                              #    objects to be serialized set safe=False
return JsonResponse([1, 2, 3], safe=False)    # ✅ ab chalega

# safe=True default KYUN? Historical security: purane browsers me top-level JSON ARRAY
# response <script src=...> se hijack ho sakta tha (JSON hijacking — Array constructor
# override). Dict top-level me valid JS statement nahi banta — safe. Modern browsers me
# yeh attack patched hai, but default conservative hai. Best practice waise bhi:
# top-level dict rakho — {'results': [...]} — future me metadata add karna easy.
```

### Shortcuts — render/redirect/get_object_or_404

```python
from django.shortcuts import render, redirect, get_object_or_404, get_list_or_404

# render = template load + context render + HttpResponse — 3 kaam ek me
return render(request, 'blog/detail.html', {'article': a}, status=200)

# redirect — 3 flavors:
return redirect('article-detail', pk=5)      # ✅ URL name + kwargs (reverse() internally)
return redirect(article)                     # model instance → uska get_absolute_url()
return redirect('/articles/5/')              # hardcoded path (avoid)
return redirect('home', permanent=True)      # 301 — SAVDHAAN: browsers aggressively
                                             # cache karte hain; galat 301 deploy kiya to
                                             # users ke browser me ATKA rahega. Default 302 safe.

# get_object_or_404 — try/except DoesNotExist boilerplate khatam
article = get_object_or_404(Article, pk=pk)                    # nahi mila → Http404
article = get_object_or_404(Article.objects.select_related('author'), pk=pk)  # queryset bhi!
# MultipleObjectsReturned catch NAHI karta — wo 500 hi hai (data bug hai, user error nahi)

items = get_list_or_404(Article, status='published')   # EMPTY list → 404 (list() + check)
```

---

## Core Concepts — Part 6: Static & Media — dev vs prod

**Pehle distinction:** **static** = TUMHARA code ka hissa (CSS/JS/logos — deploy ke time fix). **media** = USERS ka uploaded content (avatars, attachments — runtime pe badalta hai). Alag settings, alag serving, alag security model.

```python
# settings.py
STATIC_URL = 'static/'                        # URL prefix: /static/blog/style.css
STATICFILES_DIRS = [BASE_DIR / 'static']      # extra non-app static folders
STATIC_ROOT = BASE_DIR / 'staticfiles'        # collectstatic ka DESTINATION (prod only)

MEDIA_URL = 'media/'                          # URL prefix for uploads
MEDIA_ROOT = BASE_DIR / 'media'               # uploads DISK pe yahan jaate hain

# FileField/ImageField MEDIA_ROOT ke relative save karta hai:
avatar = models.ImageField(upload_to='avatars/%Y/%m/')   # media/avatars/2026/06/pic.jpg
# DB me sirf 'avatars/2026/06/pic.jpg' string; avatar.url = '/media/avatars/2026/06/pic.jpg'
```

```python
# urls.py — DEV me media serve karne ka standard helper:
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [ ... ]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# static() helper DEBUG=False me khud hi EMPTY list return karta hai — prod me no-op.
```

**runserver behavior:** `DEBUG=True` me runserver app static files (`django.contrib.staticfiles` se) **automatically** serve karta hai — isliye dev me bina kuch kiye CSS dikhta hai. Media ke liye upar wala `static()` helper chahiye. `DEBUG=False` karte hi runserver static bhi serve karna **band** — "CSS gayab ho gaya!" moment. Yeh feature hai, bug nahi: **Django prod me files serve karne ke liye design hi nahi hua** (slow, no caching headers, Python worker block hota hai).

**Whitenoise — kya hai, kab:**

```python
# pip install whitenoise
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',     # ← SecurityMiddleware ke turant baad
    ...
]
STORAGES = {  # Django 4.2+
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
```

Whitenoise = Django ke andar se hi static files **efficiently** serve karna — compression (gzip/brotli pre-compressed), far-future cache headers, manifest hashing (`style.abc123.css` — cache busting). **Kab perfect:** Heroku/Railway/Render jaisa PaaS jahan alag nginx nahi hai, small-medium traffic. **Kab S3/CDN better:** heavy traffic (CDN edge caching world-wide), bahut bada static set, ya **media files** — whitenoise media serve NAHI karta (sirf static — media ke liye S3 + django-storages, file 17).

**Prod checklist:**

1. `DEBUG = False` + `ALLOWED_HOSTS` set
2. `python manage.py collectstatic` — sab apps ka static → `STATIC_ROOT` me ek jagah
3. Static serving: nginx `location /static/ { alias ... }` YA whitenoise YA S3+CDN
4. Media serving: nginx `location /media/` YA (better) S3 + django-storages — **app server se kabhi nahi**
5. Media me user uploads = untrusted: extension/size validation, kabhi execute na hon (nginx me `location /media/ { ... }` me PHP/script handlers off), filenames sanitized (Django khud karta hai)
6. `STORAGES`/`STATICFILES_STORAGE` me Manifest storage — cache busting free

---

## Common Pitfalls

### 1. CharField me null=True

Do "empty" states (`NULL` + `''`) — queries/uniqueness ka chaos. String fields: sirf `blank=True`. (Exception: `unique=True` + optional.)

### 2. default=[] / default={} / default=timezone.now()

Mutable shared default ya import-time evaluation. Hamesha **callable bina parentheses**: `default=list`, `default=dict`, `default=timezone.now`.

### 3. JSON API me request.POST padhna

```python
def api_view(request):
    name = request.POST.get('name')    # ❌ None — JSON body POST me parse NAHI hota!
    data = json.loads(request.body)    # ✅ raw body se (ya DRF use karo — request.data)
```

### 4. on_delete=CASCADE bina soche

`Invoice.customer = FK(Customer, on_delete=models.CASCADE)` → customer delete = **paid invoices bhi delete** = accounting/legal disaster. Financial/audit refs pe `PROTECT` default rakho, CASCADE sirf truly-owned data pe.

### 5. JsonResponse(list) without safe=False

TypeError in prod jab pehli baar list return ki. Better: top-level dict hi rakho — `{'results': [...]}`.

### 6. permanent=True redirect casually

301 browser me cache hota hai — galat target deploy kiya to user ke browser me stuck, tumhare fix ke baad bhi. Default 302 rakho jab tak URL move **genuinely permanent** na ho.

### 7. App INSTALLED_APPS me add karna bhoolna

Models likhe, `makemigrations` → "No changes detected". Ya templates `TemplateDoesNotExist`. Pehla check: INSTALLED_APPS.

### 8. Templates/static me app-namespace folder skip karna

`blog/templates/detail.html` (single folder) — doosri app ka same-naam template **pehle mil gaya** to wahi render hoga (loader order). Hamesha `blog/templates/blog/detail.html`.

### 9. DEBUG=False pe "CSS gayab"

runserver ne static serving band kar di — yeh expected hai. Prod serving setup karo (whitenoise/nginx), `collectstatic` chalao. `--insecure` flag sirf quick local testing ke liye.

### 10. M2M ko shuru me plain rakhna jab extra data ki boo aa rahi thi

"Bas members chahiye" → 3 mahine baad "join date bhi chahiye" → plain M2M se `through` migration = table rename + data migration dance. Doubt ho to pehle hi explicit through model.

---

## Interview Q&A

**Q1:** Django MVT kya hai aur MVC se kaise map hota hai?
**A:** Model = data layer (same as MVC). Django ka **View = MVC ka Controller** — request process karta hai, model se data leta hai, response banata hai. Django ka **Template = MVC ka View** — presentation. Django team ke hisaab se "view" = "which data you see" (data description) aur "controller" framework khud hai (URL dispatch machinery). Isliye ise MTV (Model-Template-View) bhi kehte hain — naming alag hai, architecture MVC-family ki hi hai.

**Q2:** startproject vs startapp? INSTALLED_APPS me register karne se kya hota hai?
**A:** startproject = website container (settings.py, root urls.py, wsgi/asgi entrypoints). startapp = ek self-contained feature module (models, views, admin, migrations). Register karne se: app registry me models discovery (warna RuntimeError), migrations tracking, `APP_DIRS` template lookup, static collection, admin/commands/tests autodiscovery, `AppConfig.ready()` hook (signals yahin connect hote hain). Classic symptom of bhoolna: "No changes detected" on makemigrations.

**Q3:** null=True vs blank=True?
**A:** `null` = **DB-level** — column NULL allow karega (schema change, migration banegi). `blank` = **validation-level** — forms/serializers/full_clean empty allow karenge. CharField/TextField pe null=True avoid karo — `NULL` aur `''` do empty states ban jaate hain (query/uniqueness chaos); strings me empty = `''` convention. Date/Integer/FK optional ke liye dono chahiye: `null=True, blank=True`.

**Q4:** choices define karne ke styles aur TextChoices kyun better?
**A:** (1) Tuples list `[('draft','Draft'),...]` — legacy, magic strings. (2) `TextChoices`/`IntegerChoices` (3.0+) — enum classes: `Status.DRAFT` type-safe references, typo = AttributeError instantly (string typo silently 0 results deta). `.choices`, `.values`, `.labels` properties free. (3) `get_FOO_display()` har choices field pe auto-method — stored value se human label. Note: choices DB constraint nahi banata — hard guarantee ke liye CheckConstraint.

**Q5:** `default=list` vs `default=[]` vs `db_default`?
**A:** `default=[]` = ek hi mutable list saare instances share karte hain (Python mutable-default trap; Django W039 warning). `default=list` = callable — har instance pe fresh evaluate. Same logic se `default=timezone.now` (bina parentheses!). `db_default` (Django 5.0) DB schema me `DEFAULT` clause lagata hai — raw SQL inserts aur doosri services ko bhi milta hai, jabki `default` sirf Django ORM-created instances pe.

**Q6:** on_delete ke saare options? PROTECT vs RESTRICT difference?
**A:** CASCADE (children delete), PROTECT (ProtectedError — unconditional block), RESTRICT (RestrictedError — but agar referenced object **usi cascade operation** me waise bhi delete ho raha hai to allowed), SET_NULL (needs null=True), SET_DEFAULT, SET(callable) (sentinel pattern), DO_NOTHING (DB pe chhod do — bina DB-level handling ke IntegrityError). PROTECT = hamesha block; RESTRICT = block except same-cascade. Aur yeh Python-level enforce hota hai (Django collector) — raw SQL deletes pe nahi chalta.

**Q7:** M2M me extra fields kaise store karoge?
**A:** `through=` model — junction table explicit model banao (Membership with person FK + group FK + date_joined/role), M2M pe `through='Membership'`. Add karte time `group.members.add(p, through_defaults={'role': 'admin'})` ya direct `Membership.objects.create()`. Queries dono taraf normal + `filter(membership__role='admin')` se through-fields pe filter. Kab: jab relationship khud data carry kare (role, quantity, join date). Plain→through migration painful hai, isliye doubt ho to pehle se through.

**Q8:** related_name vs related_query_name?
**A:** `related_name` = reverse **accessor** instance pe (`user.articles.all()`; default `<model>_set`; `'+'` = disable). `related_query_name` = reverse **filter path** (`User.objects.filter(article__title=...)`; default = related_name ki value). Pattern: related_name plural ('articles' — collection accessor), related_query_name singular ('article' — readable filter path).

**Q9:** JsonResponse me safe=False kab aur kyun?
**A:** Top-level non-dict (list etc.) serialize karne ke liye — warna TypeError. Default safe=True historical JSON-hijacking concern se hai: top-level JSON array purane browsers me `<script>` include karke Array constructor override se padha ja sakta tha; dict valid JS statement nahi banta. Best practice: top-level dict hi rakho (`{'results': [...]}`) — secure + extensible (pagination metadata baad me add ho sake).

**Q10:** Static vs media, aur production me kaun serve karta hai?
**A:** Static = developer assets (CSS/JS — code ke saath deploy), media = user uploads (runtime). Dev: runserver DEBUG=True me static auto-serve karta hai, media ke liye `static(MEDIA_URL, document_root=MEDIA_ROOT)` urlpatterns helper (DEBUG=False me yeh no-op hai). Prod: `collectstatic` → STATIC_ROOT, phir nginx/whitenoise/S3+CDN serve karein — Django worker se kabhi nahi (slow, no caching). Whitenoise = in-app efficient static serving (compression + manifest hashing + cache headers) — PaaS (Heroku/Railway) pe perfect jahan nginx nahi; heavy traffic ya media files ke liye S3 + django-storages + CDN.

---

## Real-World Use Cases

### 1. SaaS order model — is file ke saare patterns ek saath

```python
class Order(TimeStampedModel):                       # abstract base (file 38)
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        CANCELLED = 'cancelled', 'Cancelled'

    customer = models.ForeignKey('Customer', on_delete=models.PROTECT,   # paid orders safe!
                                 related_name='orders', related_query_name='order')
    status = models.CharField(max_length=20, choices=Status.choices,
                              default=Status.PENDING)
    notes = models.TextField(blank=True)             # blank only — no null on text
    metadata = models.JSONField(default=dict)        # callable!
    items = models.ManyToManyField('Product', through='OrderItem')   # quantity/price through me
```

### 2. JSON API view — request/response hygiene

```python
def create_order(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    try:
        data = json.loads(request.body)              # body, NOT request.POST
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid JSON'}, status=400)
    order = Order.objects.create(customer_id=data['customer_id'])
    return JsonResponse({'id': order.id, 'status': order.status}, status=201)  # top-level dict
```

### 3. Railway/Heroku deploy — whitenoise stack

```python
# Build step: python manage.py collectstatic --noinput
# settings: whitenoise middleware + CompressedManifestStaticFilesStorage
# Media: S3 via django-storages (PaaS disk ephemeral hai — local MEDIA_ROOT deploy pe UDD jaata!)
```

---

## References

- [Django at a glance / FAQ — MVC question](https://docs.djangoproject.com/en/5.0/faq/general/#django-appears-to-be-a-mvc-framework-but-you-call-the-controller-the-view-and-the-view-the-template-how-come-you-don-t-use-the-standard-names)
- [Model field reference](https://docs.djangoproject.com/en/5.0/ref/models/fields/)
- [Enumeration types (TextChoices)](https://docs.djangoproject.com/en/5.0/ref/models/fields/#enumeration-types)
- [Many-to-many with through](https://docs.djangoproject.com/en/5.0/topics/db/models/#extra-fields-on-many-to-many-relationships)
- [Request/Response objects](https://docs.djangoproject.com/en/5.0/ref/request-response/)
- [Managing static files](https://docs.djangoproject.com/en/5.0/howto/static-files/)
- [WhiteNoise docs](https://whitenoise.readthedocs.io/)
