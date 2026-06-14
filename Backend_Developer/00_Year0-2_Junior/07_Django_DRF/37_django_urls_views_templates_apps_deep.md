# Django URLs, Views, Templates, Apps Deep — Routing Internals, FBV vs CBV, Template Engine, Reusable Apps

## Why It Matters

Yeh 4 cheezein Django ka **skeleton** hain — har request inhi se guzarti hai:

```
Request → URLconf (resolve) → View (FBV/CBV dispatch) → Template (render) → Response
```

DRF-heavy projects me bhi yeh foundation hai — admin, server-rendered internal tools, HTMX apps sab isi pe chalte hain. Interview me "as_view() internally kya karta hai?" ya "namespace kyun chahiye?" — yeh sab junior/mid level pe **guaranteed questions** hain. Aur app structure galat hua to 2 saal baad codebase unmaintainable ban jaata hai.

---

## Core Concepts — Part 1: URL Routing DEEP

### Path Converters (built-in)

```python
# urls.py
from django.urls import path

urlpatterns = [
    path('articles/<int:pk>/', views.detail),          # 42 → pk=42 (int). 'abc' → 404
    path('users/<str:username>/', views.profile),      # koi bhi non-empty string, '/' chhodke
    path('posts/<slug:slug>/', views.post),            # letters, numbers, hyphen, underscore
    path('files/<uuid:file_id>/', views.file),         # 075194d3-6885-417e-a8a8-6c931e272f00
    path('docs/<path:doc_path>/', views.doc),          # '/' INCLUDE karta hai → 'a/b/c.txt'
]
```

| Converter | Match karta hai | Python type | Example |
|---|---|---|---|
| `int` | 0 ya positive digits | `int` | `42` |
| `str` | non-empty, `/` excluded | `str` | `hello` (default agar converter na do) |
| `slug` | `[-a-zA-Z0-9_]+` | `str` | `my-post-2024` |
| `uuid` | formatted UUID (lowercase, dashes zaroori) | `uuid.UUID` | `075194d3-...` |
| `path` | non-empty, `/` **included** | `str` | `folder/sub/file.txt` |

**Key insight:** Converter sirf regex match nahi karta — **type conversion bhi karta hai**. `<int:pk>` se view me `pk` already `int` hota hai, `str` nahi. Isliye `int` converter use karo jab numeric ID ho — galat URL pe 404 milega view code chalne se pehle hi.

### Custom Converter — register_converter

Built-in converters kam pad jaayein to apna banao. Real example: `YYYY-MM` date converter (archive pages ke liye):

```python
# converters.py
import datetime


class YearMonthConverter:
    regex = r'\d{4}-\d{2}'   # URL me kya match hoga

    def to_python(self, value):
        # URL string → Python object (view ko yeh milega)
        # ValueError raise karo to match fail → Django agla pattern try karega (5.1+)
        return datetime.datetime.strptime(value, '%Y-%m').date()

    def to_url(self, value):
        # Python object → URL string (reverse() ke liye — DONO directions zaroori!)
        return value.strftime('%Y-%m')


# urls.py
from django.urls import path, register_converter
from . import converters, views

register_converter(converters.YearMonthConverter, 'yyyymm')

urlpatterns = [
    path('archive/<yyyymm:month>/', views.archive, name='archive'),
]


# View me month already datetime.date hai — parsing logic view se URL layer me shift!
def archive(request, month):
    posts = Post.objects.filter(
        created_at__year=month.year, created_at__month=month.month,
    )
    ...

# reverse bhi clean:
reverse('archive', kwargs={'month': datetime.date(2024, 6, 1)})  # → /archive/2024-06/
```

**Yeh pattern isliye powerful hai** kyunki validation + conversion **ek jagah** centralize ho jaati hai — har view me `try: datetime.strptime(...)` nahi likhna padta.

### re_path — kab use karein

```python
from django.urls import re_path

urlpatterns = [
    # Named groups (?P<name>...) view kwargs ban jaate hain — but SAB strings rahenge!
    re_path(r'^articles/(?P<year>[0-9]{4})/$', views.year_archive),

    # Legacy URL patterns jo path() se express nahi hote
    re_path(r'^(?P<lang>en|hi|fr)/docs/$', views.docs),  # sirf 3 fixed values
]
```

**Decision rule:** `path()` default rakho. `re_path` sirf tab jab: (1) legacy regex URLs migrate kar rahe ho, (2) pattern itna custom hai ki converter banana overkill hai (one-off). Agar wahi pattern **2+ jagah** use ho raha hai → custom converter banao, `re_path` nahi. Yaad rakho: `re_path` ke captured groups **hamesha str** aate hain — type conversion khud karni padegi (yeh subtle bug source hai).

### include() + app_name + namespace + reverse

```python
# blog/urls.py — app-level URLconf
from django.urls import path
from . import views

app_name = 'blog'    # ← APPLICATION namespace (app ke andar declare hota hai)

urlpatterns = [
    path('', views.PostListView.as_view(), name='list'),
    path('<int:pk>/', views.PostDetailView.as_view(), name='detail'),
]


# project/urls.py
from django.urls import path, include

urlpatterns = [
    path('blog/', include('blog.urls')),                       # namespace = 'blog' (app_name se)
    path('news/', include('blog.urls', namespace='news')),     # same app, alag INSTANCE namespace
]
```

```python
# Reverse — Python code me
from django.urls import reverse, reverse_lazy

reverse('blog:detail', kwargs={'pk': 42})    # → '/blog/42/'
reverse('news:detail', kwargs={'pk': 42})    # → '/news/42/'  (same view, alag prefix!)

# reverse_lazy — class attributes me (URLconf load hone se PEHLE evaluate na ho isliye)
class PostDeleteView(DeleteView):
    success_url = reverse_lazy('blog:list')   # plain reverse() yahan ImportError dega
```

```html
<!-- Template me -->
<a href="{% url 'blog:detail' pk=post.pk %}">{{ post.title }}</a>
<a href="{% url 'blog:detail' post.pk %}">positional bhi chalega</a>
```

**Namespace kyun zaroori?** Do apps me dono `name='detail'` ho sakta hai — bina namespace ke `reverse('detail')` **jo URLconf me pehle aaya wahi milega** (silent wrong link!). `app_name` + `'blog:detail'` se collision impossible.

### kwargs vs args in reverse()

```python
reverse('blog:detail', kwargs={'pk': 42})    # ✅ PREFERRED — explicit, readable
reverse('blog:detail', args=[42])            # chalega, but positional — pattern badla to silently galat map ho sakta hai

reverse('blog:detail', args=[42], kwargs={'pk': 42})   # ❌ ValueError — dono saath NAHI
```

**Rule:** kwargs use karo. URL pattern me parameter ka order badle to `args` wala code galat URLs banayega; `kwargs` name se match karta hai.

---

## Core Concepts — Part 2: FBV vs CBV DEEP

### Honest Decision Framework

| | FBV | CBV |
|---|---|---|
| Readability | Top-to-bottom, ek nazar me samajh aata hai | Logic 5 methods me bikhri, parent classes me chhupi |
| Reuse | Decorators/helpers se | Inheritance + mixins se (yahi main selling point) |
| Customization | Sab kuch explicit likhna padta hai | Override points (`get_queryset` etc.) ready-made |
| Learning curve | Zero | MRO + ccbv.co.uk lookup chahiye |
| Best for | One-off views, complex branching logic, webhooks | Standard CRUD, listing+pagination, "10 similar views" |

**Honest take:** CBV "advanced" nahi hai, FBV "beginner" nahi hai. CBV tab jeet-ta hai jab **pattern repeat** ho raha ho (CRUD × 10 models). FBV tab jeet-ta hai jab logic **unique** ho — CBV me unique logic thoonsna = 6 methods override karna = FBV se zyada code. Django docs khud kehte hain: dono first-class citizens hain.

### as_view() → setup → dispatch — internals flow

```python
# Jab tum likhte ho: path('x/', MyView.as_view())
# Internally yeh hota hai (simplified django/views/generic/base.py):

class View:
    @classonlymethod
    def as_view(cls, **initkwargs):
        def view(request, *args, **kwargs):
            self = cls(**initkwargs)          # 1. HAR REQUEST pe NAYA instance (thread-safe isliye!)
            self.setup(request, *args, **kwargs)   # 2. self.request/self.args/self.kwargs set
            return self.dispatch(request, *args, **kwargs)
        return view    # ← yeh closure hi URLconf me jaata hai (ek plain function!)

    def dispatch(self, request, *args, **kwargs):
        # 3. HTTP method → same-naam method pe route
        if request.method.lower() in self.http_method_names:
            handler = getattr(self, request.method.lower(), self.http_method_not_allowed)
        else:
            handler = self.http_method_not_allowed
        return handler(request, *args, **kwargs)   # 4. get()/post()/put()... call
```

**Flow yaad rakho:** `as_view()` (import time, ek baar) → per-request: `__init__` → `setup()` → `dispatch()` → `get()/post()`. 

**Do critical insights:**
1. CBV ultimately **function hi hai** — `as_view()` closure return karta hai. Isliye URLconf ko farak nahi padta FBV hai ya CBV.
2. Har request pe **fresh instance** banta hai — isliye `self.request` pe state rakhna safe hai. Lekin **class attributes mutate mat karo** (`self.some_list.append(...)` jahan `some_list` class-level hai) — woh saari requests me share hoga. Classic trap!

### Generic CBVs — har ek with example

```python
from django.views.generic import (
    TemplateView, RedirectView, ListView, DetailView,
    CreateView, UpdateView, DeleteView,
)
from django.urls import reverse_lazy


# 1. TemplateView — static-ish page with context
class AboutView(TemplateView):
    template_name = 'pages/about.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)   # super() call BHOOLNA = parent context gayab
        ctx['team_count'] = Employee.objects.count()
        return ctx


# 2. RedirectView — old URLs, counters
class OldPostRedirect(RedirectView):
    permanent = True            # 301 vs 302
    pattern_name = 'blog:detail'   # kwargs pass-through hote hain


# 3. ListView — listing + pagination FREE
class PostListView(ListView):
    model = Post
    paginate_by = 20                       # ?page=2 handling free
    context_object_name = 'posts'          # default 'object_list' / 'post_list'
    # template default: blog/post_list.html

    def get_queryset(self):
        # SABSE common override — filtering/optimization yahan
        return Post.objects.filter(status='published').select_related('author')


# 4. DetailView — single object by pk/slug
class PostDetailView(DetailView):
    model = Post
    # URLconf me <int:pk> ya <slug:slug> chahiye — DetailView khud get_object_or_404 karta hai
    # template default: blog/post_detail.html, context me 'post' + 'object'


# 5. CreateView — form display + validation + save, sab built-in
class PostCreateView(CreateView):
    model = Post
    fields = ['title', 'body']             # ya form_class = PostForm (dono NAHI)
    success_url = reverse_lazy('blog:list')

    def form_valid(self, form):
        # Save se pehle data inject karne ki SAHI jagah
        form.instance.author = self.request.user
        return super().form_valid(form)    # yeh save + redirect karta hai


# 6. UpdateView — CreateView jaisa, but existing instance pre-filled
class PostUpdateView(UpdateView):
    model = Post
    fields = ['title', 'body']

    def get_queryset(self):
        # SECURITY: sirf apne posts edit kar paaye — get_object isi qs se uthata hai
        return Post.objects.filter(author=self.request.user)

    def get_success_url(self):
        return reverse('blog:detail', kwargs={'pk': self.object.pk})


# 7. DeleteView — GET = confirmation page, POST = delete
class PostDeleteView(DeleteView):
    model = Post
    success_url = reverse_lazy('blog:list')
    # template default: blog/post_confirm_delete.html
```

**3 key override points (90% customization inhi se):**

| Override | Kab | Kya return kare |
|---|---|---|
| `get_queryset()` | Filtering, select_related, per-user scoping | QuerySet |
| `get_context_data(**kwargs)` | Template ko extra data | dict (super() ka ctx extend karke) |
| `form_valid(form)` | Save se pehle fields set (author, tenant) / side effects (email) | `super().form_valid(form)` |

### Mixins + MRO — order MATTERS

```python
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin


# ✅ SAHI — mixins LEFT side, view RIGHT side
class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    fields = ['title']
    login_url = '/login/'            # default: settings.LOGIN_URL


class PostDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Post
    permission_required = 'blog.delete_post'    # ya list/tuple of perms
    raise_exception = True           # 403 instead of login redirect


# ❌ GALAT — view pehle, mixin baad me
class Broken(CreateView, LoginRequiredMixin):
    ...
```

**Kyun order matter karta hai? MRO (Method Resolution Order).** `LoginRequiredMixin.dispatch()` auth check karke `super().dispatch()` call karta hai. Python MRO **left-to-right** chalta hai:

```
LoginRequiredMixin → PermissionRequiredMixin → DeleteView → ... → View
   (auth check)         (perm check)            (actual work)
```

Galat order me `CreateView.dispatch` ka chain mixin tak pahunchne se pehle hi response de sakta hai — **auth check skip!** Rule: **mixins always leftmost, base view rightmost.** Verify: `MyView.__mro__` print karke dekho.

```python
# Custom mixin ka pattern — dispatch ya get_queryset hook karo
class OwnerOnlyMixin:
    """Object ka owner hi access kar paaye."""
    def get_queryset(self):
        return super().get_queryset().filter(author=self.request.user)
        # 404 milega non-owner ko — 403 se better (existence leak nahi hoti)
```

### DRF Parallel — same philosophy

| Django (HTML) | DRF (JSON) | Common idea |
|---|---|---|
| `View` + dispatch | `APIView` + dispatch | HTTP method → handler routing |
| `ListView` | `ListAPIView` | `get_queryset()` override |
| `DetailView` | `RetrieveAPIView` | pk/slug se object |
| `CreateView` (form) | `CreateAPIView` (serializer) | validation → save |
| `UpdateView`/`DeleteView` | `UpdateAPIView`/`DestroyAPIView` | same |
| `form_valid()` | `perform_create(serializer)` | save-time injection hook |
| Mixins (`LoginRequiredMixin`) | `permission_classes` | access control |
| — | `ModelViewSet` (sab CRUD ek class) | Django me iska equivalent nahi |

CBV samajh liya to DRF generics free me samajh aa jaati hain — **same dispatch pattern, same override-points philosophy**.

---

## Core Concepts — Part 3: Templates basics → solid

### Variables + Filters

```html
{{ post.title }}                 <!-- attribute lookup -->
{{ post.get_absolute_url }}      <!-- method call — BINA parentheses (args wale methods call NAHI ho sakte) -->
{{ mydict.key }} {{ mylist.0 }}  <!-- dict key, list index — sab dot se -->

{{ post.created_at|date:"d M Y" }}       <!-- 12 Jun 2026 -->
{{ user.nickname|default:"Guest" }}      <!-- falsy ho to fallback -->
{{ post.body|truncatechars:120 }}        <!-- "Lorem ipsum…" -->
{{ post.body|truncatewords:20 }}
{{ count|pluralize }}                    <!-- 1 item, 2 items -->
{{ value|lower|truncatechars:50 }}       <!-- chaining — left to right -->
```

**Dot lookup order (yeh interview me poochte hain):** dict key → attribute → method call → list index. Pehla jo mile wahi use hota hai.

### Custom Filter banana

```python
# blog/templatetags/__init__.py    ← yeh file zaroori (package banane ke liye)
# blog/templatetags/blog_extras.py
from django import template

register = template.Library()


@register.filter
def rupees(value):
    """1234567 → ₹12,34,567 (Indian comma style)"""
    s = str(int(value))
    if len(s) <= 3:
        return f'₹{s}'
    last3, rest = s[-3:], s[:-3]
    groups = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return '₹' + ','.join(groups + [last3])


@register.filter(name='startswith')
def startswith(value, arg):          # filter with argument: {{ name|startswith:"Mr" }}
    return str(value).startswith(arg)


@register.simple_tag
def current_year():                  # tag (filter nahi): {% current_year %}
    import datetime
    return datetime.date.today().year
```

```html
{% load blog_extras %}     <!-- har template me load karna padta hai jo use kare -->
{{ product.price|rupees }}
```

**Trap:** `templatetags` folder banane ke baad **server restart zaroori** — Django startup pe hi discover karta hai. Aur app `INSTALLED_APPS` me honi chahiye.

### Tags — if / for / with / url / csrf_token

```html
{% if user.is_authenticated and user.is_staff %}
    Staff panel
{% elif user.is_authenticated %}
    Welcome {{ user.username }}
{% else %}
    <a href="{% url 'login' %}">Login</a>
{% endif %}

{% for post in posts %}
    {{ forloop.counter }}. {{ post.title }}        <!-- 1-indexed; counter0 = 0-indexed -->
    {% if forloop.first %}(latest){% endif %}
{% empty %}
    Koi post nahi hai.                             <!-- empty queryset ka clean handling -->
{% endfor %}

{% with total=order.items.count %}                 <!-- expensive lookup EK baar — cache in variable -->
    {{ total }} items — {% if total > 10 %}bulk discount!{% endif %}
{% endwith %}

<form method="post">{% csrf_token %}...</form>     <!-- POST form me hamesha -->
```

### Template Inheritance — base.html pattern

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}MySite{% endblock %}</title>
    {% block extra_css %}{% endblock %}
</head>
<body>
    {% include 'partials/navbar.html' %}
    <main>{% block content %}{% endblock %}</main>
    <footer>{% block footer %}© {% now "Y" %}{% endblock %}</footer>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

```html
<!-- blog/templates/blog/post_list.html -->
{% extends 'base.html' %}      <!-- FIRST tag honi chahiye, warna error -->

{% block title %}Blog — {{ block.super }}{% endblock %}   <!-- block.super = parent ka content append -->

{% block content %}
    {% for post in posts %}
        {% include 'blog/partials/post_card.html' with post=post show_author=True only %}
    {% endfor %}
{% endblock %}
```

**`include` with context:** `with x=y` se explicit variables pass karo; `only` lagao to **sirf wahi variables** milenge (parent context leak nahi hoga — reusable partials ke liye best practice, warna partial silently parent ke variables pe depend karne lagta hai).

**Pattern:** 3-level hierarchy common hai — `base.html` → `base_dashboard.html` (sidebar layout) → actual pages. Blocks = override points, exactly CBV methods jaise.

### Context Processors — har template me available data

```python
# core/context_processors.py
def site_settings(request):
    """Har template render me yeh dict merge hota hai."""
    return {
        'SITE_NAME': 'MyApp',
        'cart_count': request.session.get('cart_count', 0),
    }


# settings.py → TEMPLATES[0]['OPTIONS']['context_processors'] me add:
# 'core.context_processors.site_settings',
```

Built-in walon se hi `{{ user }}`, `{{ request }}`, `{{ messages }}` har template me milte hain (`auth`, `request`, `messages` processors). **Warning:** context processor **har render pe chalta hai** — heavy query mat daalo, warna har page slow. Query lagani hi hai to cache karo.

### autoescape + |safe + XSS danger

```html
{{ user_comment }}
<!-- Input: <script>alert('xss')</script> -->
<!-- Output: &lt;script&gt;alert('xss')&lt;/script&gt;  ← Django ne ESCAPE kar diya, default ON -->

{{ user_comment|safe }}
<!-- ☠️ Script CHAL JAYEGA. |safe = "main guarantee deta hoon yeh safe hai" -->

{% autoescape off %} ... {% endautoescape %}   <!-- block-level off — almost never karo -->
```

**Rule:** `|safe` **sirf** us content pe jo (a) tumne khud generate kiya, ya (b) sanitize ho chuka hai (`bleach`/`nh3` library se whitelist-based cleaning). User input pe directly `|safe` = stored XSS = attacker har visitor ke browser me JS chala sakta hai (session theft, fake login forms). Python side me safe markup banana ho to `format_html()` use karo, string concat + `mark_safe()` nahi.

### Template Resolution Order — DIRS vs APP_DIRS

```python
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],   # 1️⃣ PEHLE yahan dhundhega (project-level)
    'APP_DIRS': True,                   # 2️⃣ phir har app ke templates/ me, INSTALLED_APPS ke ORDER me
}]
```

**Search order:** `DIRS` → phir har installed app ka `templates/` folder, **INSTALLED_APPS ke order me. Pehla match jeet gaya.** Isi se kaam ka trick: third-party app (e.g. `django-allauth`) ka template override karna ho to project-level `templates/` me **same relative path** pe file rakh do — tumhari file pehle milegi. Lekin yahi trick galti se bhi fire kar sakta hai — do apps me same template path ho to silent wrong template render hota hai. Isliye namespacing: `blog/templates/blog/list.html`, NOT `blog/templates/list.html`.

---

## Core Concepts — Part 4: App Structure & Reusability

### startapp Anatomy — har file ka purpose

```
blog/
├── __init__.py        # Python package marker
├── admin.py           # admin registrations — ModelAdmin classes
├── apps.py            # AppConfig — app metadata + ready() hook
├── migrations/        # schema history — KABHI delete mat karo casually
├── models.py          # data layer — single source of truth
├── tests.py           # tests (bade app me tests/ package banao)
└── views.py           # request handlers

# Jo files TUM add karte ho (convention, startapp nahi banata):
├── urls.py            # app-level URLconf + app_name
├── forms.py           # Forms/ModelForms
├── serializers.py     # DRF serializers
├── services.py        # business logic (neeche debate dekho)
├── managers.py        # custom managers/querysets
├── templatetags/      # custom filters/tags
└── templates/blog/    # NAMESPACED templates — double folder is intentional!
```

### AppConfig + ready() — signals ki SAHI jagah

```python
# blog/apps.py
from django.apps import AppConfig


class BlogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'blog'
    verbose_name = 'Blog & Articles'    # admin me display name

    def ready(self):
        # ✅ Signals YAHAN import/register karo
        from . import signals  # noqa: F401
        # Import hone se hi @receiver decorators register ho jaate hain
```

**Kyun `ready()` hi sahi jagah hai?**
- `models.py` me register karo → circular imports ka khatra + models.py ka kaam nahi hai yeh
- `urls.py` me → tab register hoga jab URLconf load ho — management commands me URLs load nahi hote, signals miss!
- `ready()` → Django **app registry ready hone pe guaranteed ek baar** call karta hai. Yahi official jagah hai.

**ready() ke traps:** (1) yahan DB query mat karo — migrations ke time DB schema ready nahi hota; (2) `runserver` autoreload me `ready()` do baar chal sakta hai — idempotent rakho; (3) module top-level pe signals import mat karo `apps.py` me — `ready()` ke **andar** karo.

### Fat Models vs services.py — the debate

```python
# Approach 1: FAT MODEL — logic model pe methods me
class Order(models.Model):
    def mark_paid(self, payment_ref):
        self.status = 'paid'
        self.payment_ref = payment_ref
        self.save(update_fields=['status', 'payment_ref'])
        send_receipt_email.delay(self.pk)      # hmm... email model me? 🤔


# Approach 2: SERVICES — logic plain functions me
# blog/services.py
def mark_order_paid(*, order: Order, payment_ref: str) -> Order:
    """Keyword-only args = call sites readable rehte hain."""
    order.status = 'paid'
    order.payment_ref = payment_ref
    order.save(update_fields=['status', 'payment_ref'])
    send_receipt_email.delay(order.pk)
    inventory_release(order=order)             # multi-model orchestration natural lagti hai
    return order
```

**Honest framework:**
- **Fat model** jab: logic **sirf us model ke apne data** pe hai (`order.total`, `user.full_name`, `post.is_published`). Django ka original philosophy yahi hai.
- **services.py** jab: logic **multiple models touch** karta hai, ya **external systems** (email, payment gateway, Celery) involve hain. Model method me payment gateway call karna = model untestable + import tangles.
- **View me business logic = dono approaches me GALAT.** View sirf orchestrate kare: validate → service/model call → response. Views me logic likhoge to woh management command/Celery task/DRF view se reuse nahi hogi.
- Industry me HackSoft styleguide ne services pattern popular kiya — but chhote project me dono ka mix pragmatic hai. Dogma mat banao.

### Reusable App Checklist

Ek app tabhi "reusable" hai jab doosre project me drop karke chal jaaye:

1. **Apna `urls.py` + `app_name`** — host project sirf `include('blog.urls')` kare, URLs ka internal naming tumhara namespace protect kare.
2. **Templates namespaced** — `blog/templates/blog/x.html`. Bina namespace ke host project ke templates se collision.
3. **Static bhi namespaced** — `blog/static/blog/style.css`, same reason.
4. **Swappable settings with defaults:**
```python
# blog/conf.py
from django.conf import settings

def get_posts_per_page():
    return getattr(settings, 'BLOG_POSTS_PER_PAGE', 20)   # host override kar sake, default ho
```
5. **`settings.AUTH_USER_MODEL` use karo**, direct `from django.contrib.auth.models import User` **kabhi nahi** — custom user model wale projects me tumhari app toot jayegi:
```python
author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
```
6. **Hard-coded URLs nahi** — hamesha `reverse()`/`{% url %}`.
7. **Migrations included** — app ke saath ship karo.

### Project Layout — settings split (base/dev/prod)

```
myproject/
├── config/                    # 'myproject' naam ki jagah 'config' — universal convention ban raha hai
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py            # common: INSTALLED_APPS, MIDDLEWARE, TEMPLATES
│   │   ├── dev.py             # DEBUG=True, sqlite/local pg, debug toolbar
│   │   └── prod.py            # DEBUG=False, env-driven secrets, security headers
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── apps/                      # (optional) saari apps ek folder me
│   ├── blog/
│   └── accounts/
├── templates/                 # project-level overrides (DIRS)
├── static/
└── manage.py
```

```python
# config/settings/dev.py
from .base import *            # noqa

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']
INSTALLED_APPS += ['debug_toolbar']


# config/settings/prod.py
import os
from .base import *            # noqa

DEBUG = False
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']    # crash if missing — yahi chahiye, silent default NAHI
ALLOWED_HOSTS = os.environ['ALLOWED_HOSTS'].split(',')
SECURE_SSL_REDIRECT = True
```

```bash
# Kaunsi settings use ho — env var se
export DJANGO_SETTINGS_MODULE=config.settings.prod
# dev me manage.py me default config.settings.dev set kar do
```

**Kyun split?** Single `settings.py` me `if DEBUG:` branches ka jungle ban jaata hai, aur prod secret galti se dev me leak/dev shortcut prod me chala jaata hai. Split + env vars = 12-factor compliant (detail file 23 me).

---

## Common Pitfalls

### 1. Trailing slash mismatch

```python
path('blog', ...)     # /blog/ pe 404! Django convention: trailing slash WITH APPEND_SLASH redirect
path('blog/', ...)    # ✅ — /blog pe aaya to 301 redirect /blog/ pe (sirf GET; POST data redirect me LOST)
```

### 2. URLs ka order matters (first match wins)

```python
urlpatterns = [
    path('posts/<str:username>/', ...),   # yeh 'posts/archive/' ko bhi kha jayega!
    path('posts/archive/', ...),          # kabhi reach hi nahi hoga
]
# Fix: specific patterns PEHLE, generic baad me
```

### 3. CBV class attribute pe mutable state

```python
class SearchView(ListView):
    filters = []    # ❌ class-level — SAARI requests share karengi, memory leak + race
    def get(self, request):
        self.filters.append(request.GET.get('q'))   # grows forever!
# Fix: setup()/get() me self.filters = [] (instance pe) banao
```

### 4. `reverse()` at module level

```python
class MyView(CreateView):
    success_url = reverse('blog:list')        # ❌ ImproperlyConfigured — URLconf abhi loaded nahi
    success_url = reverse_lazy('blog:list')   # ✅
```

### 5. get_context_data me super() bhoolna

```python
def get_context_data(self, **kwargs):
    return {'extra': 1}    # ❌ object_list/paginator/form sab GAYAB — template silently khali
    # ✅ ctx = super().get_context_data(**kwargs); ctx['extra'] = 1; return ctx
```

### 6. Template me silent failures

`{{ post.titel }}` (typo) → error NAHI aata, bas **khali render** hota hai. Django templates by-design forgiving hain. Debug: `'OPTIONS': {'string_if_invalid': 'INVALID[%s]'}` dev me lagao (kuch admin templates isse toot sakte hain, isliye sirf debugging ke liye).

### 7. Non-namespaced templates

`blog/templates/list.html` rakha, doosri app me bhi `list.html` tha → INSTALLED_APPS order ke hisaab se **galat template chupchaap render**. Hamesha `blog/templates/blog/list.html`.

### 8. LoginRequiredMixin ko decorator ki tarah lagana

```python
@login_required          # ❌ class pe directly NAHI lagta (woh function decorator hai)
class MyView(View): ...

# ✅ Mixin use karo, ya:
from django.utils.decorators import method_decorator
@method_decorator(login_required, name='dispatch')
class MyView(View): ...
```

---

## Interview Q&A

**Q1:** `path()` vs `re_path()` — kab kya?
**A:** `path()` default — readable, converters type conversion bhi karte hain (`<int:pk>` se int milta hai). `re_path()` sirf jab pattern converters se express na ho (legacy regex URLs, one-off complex patterns). Pattern reuse ho raha ho to custom converter (`register_converter`) better hai — validation+conversion centralize hoti hai. `re_path` ke captured groups hamesha string aate hain — yeh common bug source hai.

**Q2:** `as_view()` internally kya karta hai?
**A:** Closure (plain function) return karta hai jo URLconf me jaata hai. Har request pe: naya class instance banata hai (thread-safety isliye), `setup()` se `self.request/args/kwargs` set karta hai, phir `dispatch()` call hota hai jo `request.method` ke basis pe `get()`/`post()` etc. pe route karta hai. Key point: CBV bhi end me function hi hai, aur per-request fresh instance ka matlab instance state safe hai but class attributes shared hain.

**Q3:** URL namespace kyun chahiye? `app_name` vs `namespace` ka difference?
**A:** Do apps me same `name='detail'` ho sakta hai — bina namespace `reverse('detail')` ambiguous hai (jo pehle mila wahi). `app_name` = application namespace, app ke `urls.py` me declare hota hai. `namespace=` in `include()` = instance namespace — same app ko multiple URLs pe mount karne ke liye (`/blog/` aur `/news/` dono same app). Reverse: `reverse('blog:detail', kwargs={'pk': 1})`.

**Q4:** FBV vs CBV — tumhara decision framework?
**A:** CBV jab pattern repeat ho (standard CRUD across models — generic views + mixins se reuse). FBV jab logic unique/branching-heavy ho — CBV me unique logic ke liye 5-6 methods override karna FBV se zyada code ban jaata hai. Neither is "more advanced." Webhooks/one-off endpoints → FBV; 10 models ka admin-like CRUD → CBV.

**Q5:** Mixin order kyun matter karta hai?
**A:** Python MRO left-to-right hai. `LoginRequiredMixin.dispatch()` auth check karke `super().dispatch()` call karta hai — mixin leftmost hoga tabhi uska dispatch pehle chalega. Galat order (view pehle, mixin baad) me auth check skip ho sakta hai. Rule: mixins left, base generic view rightmost. `MyView.__mro__` se verify karo.

**Q6:** `form_valid()` vs `get_queryset()` override kab?
**A:** `get_queryset()` — read scope control: filtering, select_related, per-user data scoping (UpdateView/DeleteView me security ke liye bhi — get_object isi se uthata hai). `form_valid(form)` — write-time injection: `form.instance.author = self.request.user` save se pehle, ya side effects (email/Celery). `form_valid` me `super()` call zaroori — wahi save+redirect karta hai.

**Q7:** Template autoescaping kya hai, `|safe` kab dangerous?
**A:** Django by default `< > & " '` escape karta hai — XSS protection. `|safe` escaping band karta hai. User-generated content pe `|safe` = stored XSS (attacker ka `<script>` har visitor pe chalega). Sirf sanitized HTML (bleach/nh3 whitelist) ya self-generated markup pe use karo. Python side pe `format_html()` use karo, `mark_safe()` + string concat nahi.

**Q8:** Template resolution order? Third-party app ka template override kaise karoge?
**A:** Pehle `TEMPLATES['DIRS']` (project-level), phir `APP_DIRS` — har app ka `templates/`, INSTALLED_APPS ke order me. First match wins. Override: project-level `templates/` me same relative path pe file rakho (e.g. `templates/account/login.html` for allauth) — DIRS pehle check hota hai. Isi liye apps ko templates namespace karna zaroori hai (`app/templates/app/`).

**Q9:** Signals register karne ki sahi jagah aur kyun?
**A:** `AppConfig.ready()` me import karo (`from . import signals`). models.py me circular import risk, urls.py me management commands ke time load hi nahi hota. `ready()` app registry complete hone pe guaranteed call hota hai. Traps: ready() me DB queries nahi (migrate time schema nahi hota), idempotent rakho (autoreload double-call).

**Q10:** Fat models vs services — kya use karte ho?
**A:** Single-model, own-data logic → model methods/properties (Django philosophy). Multi-model orchestration ya external systems (payments, email, Celery) → `services.py` plain functions with keyword-only args. Views me business logic kabhi nahi — woh reuse nahi hoti (Celery task/management command se call nahi kar sakte). Pragmatic mix theek hai, dogma nahi.

---

## References

- [URL dispatcher](https://docs.djangoproject.com/en/5.0/topics/http/urls/)
- [Class-based views](https://docs.djangoproject.com/en/5.0/topics/class-based-views/)
- [ccbv.co.uk](https://ccbv.co.uk/) — har CBV ka full method/attribute flattened view (bookmark karo!)
- [Template language](https://docs.djangoproject.com/en/5.0/ref/templates/language/)
- [Applications (AppConfig)](https://docs.djangoproject.com/en/5.0/ref/applications/)
- [HackSoft Django Styleguide](https://github.com/HackSoftware/Django-Styleguide) — services pattern
