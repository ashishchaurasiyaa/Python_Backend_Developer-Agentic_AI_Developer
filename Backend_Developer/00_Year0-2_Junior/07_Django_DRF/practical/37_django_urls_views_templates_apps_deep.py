"""
Django URLs, Views, Templates & Apps — Deep Dive
=================================================
Illustrative production-quality module covering:

  1. URL routing internals — path converters (built-in + custom), re_path, include,
     namespace, reverse / reverse_lazy.
  2. FBV vs CBV — as_view() internals, generic CBVs (Template/Redirect/List/Detail/
     Create/Update/Delete), mixin ordering & MRO, OwnerOnly custom mixin.
  3. Template engine — custom filter/tag, context processors, autoescape/XSS rules,
     template resolution order, inheritance & partials.
  4. App structure — AppConfig.ready() signals pattern, fat-model vs services.py,
     reusable-app checklist, settings split (base/dev/prod).

Run (syntax-only, no Django project needed):
    python3 -m py_compile 37_django_urls_views_templates_apps_deep.py

Django docs referenced: 5.x URLconf, CBV, template language, AppConfig.
ccbv.co.uk — bookmark for every CBV's full method/attribute tree.
"""

# pip install django djangorestframework
import datetime
import re


# ===========================================================================
# SECTION 1 — URL ROUTING INTERNALS
# ===========================================================================

# ---------------------------------------------------------------------------
# 1a. Built-in path converters
# ---------------------------------------------------------------------------
#
# from django.urls import path
#
# urlpatterns = [
#     path('articles/<int:pk>/',      views.detail),    # int: type-converts to int, non-digits → 404
#     path('users/<str:username>/',   views.profile),   # any non-empty str excluding '/'
#     path('posts/<slug:slug>/',      views.post),      # [-a-zA-Z0-9_]+
#     path('files/<uuid:file_id>/',   views.file_view), # formatted UUID → uuid.UUID object
#     path('docs/<path:doc_path>/',   views.doc),       # includes '/' → 'folder/sub/file.txt'
# ]
#
# Key insight: converters do TYPE CONVERSION, not just regex matching.
# <int:pk> means the view receives an int, never a string.
# Wrong format → 404 before view code executes — validation is free.

# ---------------------------------------------------------------------------
# 1b. Custom URL converter — YearMonth (archive pages)
# ---------------------------------------------------------------------------

class YearMonthConverter:
    """
    Matches YYYY-MM in the URL and delivers a datetime.date to the view.

    Register with:
        from django.urls import register_converter
        register_converter(YearMonthConverter, 'yyyymm')

    URL pattern:
        path('archive/<yyyymm:month>/', views.archive, name='archive')

    Reverse:
        reverse('archive', kwargs={'month': datetime.date(2024, 6, 1)})
        # → /archive/2024-06/

    Benefit: validation + conversion centralised here; every view that uses
    <yyyymm:month> gets a date object — no try/strptime scattered in views.
    """

    regex = r'\d{4}-\d{2}'  # what Django matches in the URL string

    def to_python(self, value: str) -> datetime.date:
        """URL string → Python object passed to view kwarg."""
        # ValueError causes Django to try the next URL pattern (Django 5+)
        return datetime.datetime.strptime(value, '%Y-%m').date()

    def to_url(self, value: datetime.date) -> str:
        """Python object → URL string (used by reverse())."""
        return value.strftime('%Y-%m')


# ---------------------------------------------------------------------------
# 1c. re_path — when and why (almost never)
# ---------------------------------------------------------------------------
#
# from django.urls import re_path
#
# urlpatterns = [
#     # Named groups (?P<name>...) become view kwargs — but ALWAYS strings.
#     re_path(r'^articles/(?P<year>[0-9]{4})/$', views.year_archive),
#
#     # Language-prefix route with fixed set of values
#     re_path(r'^(?P<lang>en|hi|fr)/docs/$', views.docs),
# ]
#
# Decision rule:
#   - path()    → default; readable, type-converts automatically.
#   - re_path   → only for legacy patterns or one-off complexity that a
#                 custom converter would over-engineer.
#   - If the same pattern appears in 2+ places → write a converter instead.
#   - re_path captured groups are ALWAYS str → silent type bugs if you forget.

# ---------------------------------------------------------------------------
# 1d. include() + namespace + reverse / reverse_lazy
# ---------------------------------------------------------------------------
#
# --- blog/urls.py ---
#
# app_name = 'blog'   # APPLICATION namespace — declared once inside the app
#
# urlpatterns = [
#     path('',          PostListView.as_view(),   name='list'),
#     path('<int:pk>/', PostDetailView.as_view(), name='detail'),
# ]
#
# --- config/urls.py ---
#
# urlpatterns = [
#     path('blog/', include('blog.urls')),                        # namespace = 'blog'
#     path('news/', include('blog.urls', namespace='news')),      # INSTANCE namespace
# ]
#
# Reverse in Python:
#   reverse('blog:detail', kwargs={'pk': 42})   → '/blog/42/'
#   reverse('news:detail', kwargs={'pk': 42})   → '/news/42/'
#
# reverse_lazy — use in class attributes (evaluated before URLconf loads):
#   success_url = reverse_lazy('blog:list')
#
# In templates:
#   {% url 'blog:detail' pk=post.pk %}
#
# Why namespaces matter:
#   Without them, two apps both naming a view 'detail' → reverse('detail')
#   silently returns whichever URLconf was registered first. Bug with no
#   error message. Always namespace.
#
# kwargs vs args in reverse():
#   reverse('blog:detail', kwargs={'pk': 42})  ← PREFERRED; name-matched
#   reverse('blog:detail', args=[42])           ← positional; breaks silently
#                                                  if URL pattern order changes


# ---------------------------------------------------------------------------
# 1e. Common URL pitfalls (reference)
# ---------------------------------------------------------------------------

URL_PITFALLS = {
    'trailing_slash': (
        "path('blog', ...)  misses /blog/ — Django's APPEND_SLASH=True issues "
        "a 301 redirect only for GET; POST data is lost on redirect. "
        "Convention: always include trailing slash: path('blog/', ...)"
    ),
    'order_matters': (
        "First match wins. path('posts/<str:username>/', ...) swallows "
        "'posts/archive/' — place specific patterns BEFORE generic ones."
    ),
    'reverse_at_module_level': (
        "reverse('blog:list') at class attribute level raises ImproperlyConfigured "
        "because URLconf has not loaded yet. Use reverse_lazy() instead."
    ),
}


# ===========================================================================
# SECTION 2 — FBV vs CBV DEEP
# ===========================================================================

# ---------------------------------------------------------------------------
# 2a. as_view() / dispatch internals — simplified reproduction
# ---------------------------------------------------------------------------

class _ViewBase:
    """
    Minimal reproduction of django.views.generic.base.View internals.
    Shows exactly what as_view() / setup() / dispatch() do — the three
    questions interviewers ask about CBVs.
    """

    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    @classmethod
    def as_view(cls, **initkwargs):
        """
        Called ONCE at import/server startup when the URLconf is loaded.
        Returns a plain closure — this is what goes into urlpatterns.

        Critical: every request creates a FRESH instance (thread-safe).
        """
        def view(request, *args, **kwargs):
            self = cls(**initkwargs)            # new instance per request
            self.setup(request, *args, **kwargs)
            return self.dispatch(request, *args, **kwargs)

        view.view_class = cls
        view.view_initkwargs = initkwargs
        return view                             # plain function → URLconf-safe

    def setup(self, request, *args, **kwargs):
        """Bind request/args/kwargs onto self so all methods share them."""
        self.request = request
        self.args = args
        self.kwargs = kwargs

    def dispatch(self, request, *args, **kwargs):
        """Route HTTP method → same-named instance method."""
        method_name = request.method.lower()
        if method_name in self.http_method_names:
            handler = getattr(self, method_name, self._http_method_not_allowed)
        else:
            handler = self._http_method_not_allowed
        return handler(request, *args, **kwargs)

    def _http_method_not_allowed(self, request, *args, **kwargs):
        raise NotImplementedError(
            f"Method '{request.method}' not allowed on {self.__class__.__name__}"
        )


# ---------------------------------------------------------------------------
# 2b. Mutable class-attribute trap (classic Django CBV bug)
# ---------------------------------------------------------------------------

class _BrokenSearchView(_ViewBase):
    """
    WRONG pattern — class-level mutable list is shared across ALL requests.
    In production this leaks data across users and grows unbounded.
    """
    filters: list = []  # ← shared between every instance / every request

    def get(self, request, *args, **kwargs):
        self.filters.append(request.GET.get('q', ''))  # mutates the class list!
        return {'filters': self.filters}


class _CorrectSearchView(_ViewBase):
    """
    CORRECT — instance-level list assigned in get() (or setup()) so each
    request has its own fresh copy.
    """

    def get(self, request, *args, **kwargs):
        self.filters = []                               # instance attribute, not class
        self.filters.append(request.GET.get('q', ''))
        return {'filters': self.filters}


# ---------------------------------------------------------------------------
# 2c. Generic CBV showcase — annotated patterns
# ---------------------------------------------------------------------------
#
# Full imports used in a real views.py:
#
# from django.views.generic import (
#     TemplateView, RedirectView, ListView, DetailView,
#     CreateView, UpdateView, DeleteView,
# )
# from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
# from django.urls import reverse, reverse_lazy
#
#
# # 1. TemplateView — static-ish page that needs a small amount of context
# class AboutView(TemplateView):
#     template_name = 'pages/about.html'
#
#     def get_context_data(self, **kwargs):
#         ctx = super().get_context_data(**kwargs)   # always call super() — never skip
#         ctx['team_count'] = Employee.objects.count()
#         return ctx
#
#
# # 2. RedirectView — permanent/temporary URL redirect; kwargs pass through automatically
# class OldPostRedirect(RedirectView):
#     permanent = True             # 301; False → 302
#     pattern_name = 'blog:detail'
#
#
# # 3. ListView — built-in queryset + ?page=N pagination
# class PostListView(ListView):
#     model = Post
#     paginate_by = 20
#     context_object_name = 'posts'       # default: 'object_list' / 'post_list'
#     # default template: blog/post_list.html
#
#     def get_queryset(self):
#         # Most common override: filter + optimise N+1
#         return Post.objects.filter(status='published').select_related('author')
#
#
# # 4. DetailView — single object by pk or slug; calls get_object_or_404 internally
# class PostDetailView(DetailView):
#     model = Post
#     # URL must contain <int:pk> OR <slug:slug>
#     # context keys: 'post' (model name) and 'object'
#
#
# # 5. CreateView — form display + validation + save; 3 lifecycle hooks
# class PostCreateView(LoginRequiredMixin, CreateView):
#     model = Post
#     fields = ['title', 'body']               # or form_class = PostForm; not both
#     success_url = reverse_lazy('blog:list')
#
#     def form_valid(self, form):
#         form.instance.author = self.request.user    # inject before save
#         return super().form_valid(form)             # save + redirect
#
#
# # 6. UpdateView — like CreateView but pre-fills from existing instance
# class PostUpdateView(LoginRequiredMixin, UpdateView):
#     model = Post
#     fields = ['title', 'body']
#
#     def get_queryset(self):
#         # SECURITY: get_object() pulls from this queryset —
#         # non-owners get 404 (existence not leaked vs 403)
#         return Post.objects.filter(author=self.request.user)
#
#     def get_success_url(self):
#         return reverse('blog:detail', kwargs={'pk': self.object.pk})
#
#
# # 7. DeleteView — GET shows confirmation template; POST deletes
# class PostDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
#     model = Post
#     permission_required = 'blog.delete_post'
#     raise_exception = True           # 403 instead of redirect to login
#     success_url = reverse_lazy('blog:list')
#     # default template: blog/post_confirm_delete.html

# ---------------------------------------------------------------------------
# 2d. Mixin ordering — MRO enforces security chain
# ---------------------------------------------------------------------------
#
# CORRECT — mixins LEFT, base view RIGHT
# class PostCreateView(LoginRequiredMixin, CreateView): ...
#
# MRO chain:
#   LoginRequiredMixin → CreateView → ... → View
#   dispatch order: auth-check → actual work   ← safe
#
# WRONG — view before mixin
# class Broken(CreateView, LoginRequiredMixin): ...
#
# MRO chain:
#   CreateView → LoginRequiredMixin → ... → View
#   CreateView.dispatch may short-circuit before mixin fires → auth skip!
#
# Debug: print(PostCreateView.__mro__) and read left to right.
#
# PermissionRequiredMixin + LoginRequiredMixin together:
# class PostDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
#     permission_required = 'blog.delete_post'
#     raise_exception = True


# ---------------------------------------------------------------------------
# 2e. Custom mixin — owner-only queryset scoping
# ---------------------------------------------------------------------------

class OwnerOnlyMixin:
    """
    Restrict access to objects owned by the current user.

    Use with UpdateView / DeleteView (any view that calls get_object()).
    Non-owners receive 404 — existence is not revealed (vs 403 which
    confirms the object exists but the user cannot access it).

    Usage:
        class PostUpdateView(OwnerOnlyMixin, LoginRequiredMixin, UpdateView):
            model = Post
            ...
    """

    def get_queryset(self):
        qs = super().get_queryset()
        # Assumes the model has an 'author' FK to the user model.
        # Adjust field name (owner, created_by, user, tenant_id …) per model.
        return qs.filter(author=self.request.user)


# ---------------------------------------------------------------------------
# 2f. Function-based view (FBV) — when FBV wins
# ---------------------------------------------------------------------------
#
# FBV is the right choice when logic is unique or heavily branched.
# Forcing it into CBV overrides costs more code, not less.
#
# def webhook_github(request):
#     """
#     GitHub webhook — multimethod handling, signature validation,
#     conditional dispatch to different parsers.  FBV is clearer here.
#     """
#     if request.method != 'POST':
#         from django.http import HttpResponseNotAllowed
#         return HttpResponseNotAllowed(['POST'])
#
#     signature = request.headers.get('X-Hub-Signature-256', '')
#     if not _verify_signature(request.body, signature):
#         from django.http import HttpResponseForbidden
#         return HttpResponseForbidden('Bad signature')
#
#     payload = json.loads(request.body)
#     event = request.headers.get('X-GitHub-Event', '')
#
#     if event == 'push':
#         handle_push(payload)
#     elif event == 'pull_request':
#         handle_pr(payload)
#
#     from django.http import HttpResponse
#     return HttpResponse(status=204)


# ---------------------------------------------------------------------------
# 2g. DRF parallel — same dispatch philosophy
# ---------------------------------------------------------------------------

DRF_PARALLEL = {
    'View → APIView':           'HTTP method routing via dispatch(); same internals',
    'ListView':                 'ListAPIView  — override get_queryset()',
    'DetailView':               'RetrieveAPIView — pk/slug → get_object()',
    'CreateView (form)':        'CreateAPIView (serializer) — validation → save',
    'UpdateView/DeleteView':    'UpdateAPIView / DestroyAPIView — same pattern',
    'form_valid(form)':         'perform_create(serializer) — save-time injection',
    'LoginRequiredMixin':       'permission_classes = [IsAuthenticated]',
    'No Django equivalent':     'ModelViewSet — all CRUD in one class via router',
}


# ===========================================================================
# SECTION 3 — TEMPLATE ENGINE (Python-side logic)
# ===========================================================================

# ---------------------------------------------------------------------------
# 3a. Custom template filter and tag library
# ---------------------------------------------------------------------------
#
# File layout:
#   blog/
#   └── templatetags/
#       ├── __init__.py       ← must exist (makes it a Python package)
#       └── blog_extras.py    ← import name used in {% load blog_extras %}
#
# After adding/changing templatetags, restart the dev server — Django
# discovers them at startup only.  App must be in INSTALLED_APPS.

# Simulated register object for illustration (real: from django import template)
class _TemplateLibrary:
    """Stand-in for django.template.Library — illustrates the decorator API."""

    def filter(self, func=None, *, name=None):
        def decorator(f):
            f._is_filter = True
            f._filter_name = name or f.__name__
            return f
        return decorator(func) if func else decorator

    def simple_tag(self, func):
        func._is_tag = True
        return func


register = _TemplateLibrary()


@register.filter
def rupees(value: int) -> str:
    """
    Format an integer as an Indian-style currency string.

    Usage in template:
        {{ product.price|rupees }}   →  ₹12,34,567

    Indian numbering: last 3 digits grouped, then groups of 2 leftward.
    """
    s = str(int(value))
    if len(s) <= 3:
        return f'₹{s}'
    last3 = s[-3:]
    rest = s[:-3]
    groups: list[str] = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return '₹' + ','.join(groups + [last3])


@register.filter(name='startswith')
def startswith_filter(value: str, arg: str) -> bool:
    """
    Test whether a string starts with a prefix.

    Usage in template:
        {% if user.role|startswith:"admin" %}

    Note: Django template filters cannot use Python's built-in 'startswith'
    method because template method calls cannot pass arguments.
    """
    return str(value).startswith(arg)


@register.simple_tag
def current_year() -> int:
    """
    Return the current calendar year.

    Usage:
        {% load blog_extras %}
        {% current_year %}   →  2026
    """
    return datetime.date.today().year


# ---------------------------------------------------------------------------
# 3b. Context processor — data available in every template
# ---------------------------------------------------------------------------

def site_settings_processor(request) -> dict:
    """
    Context processor — returned dict is merged into every template context
    automatically (add to TEMPLATES[0]['OPTIONS']['context_processors']).

    Result: {{ SITE_NAME }} and {{ cart_count }} work in any template
    without the view explicitly passing them.

    Warning: this runs on EVERY render — do not place expensive queries here
    without caching.  Use django.core.cache or request-scoped memoisation.

    settings.py addition:
        TEMPLATES = [{
            ...
            'OPTIONS': {
                'context_processors': [
                    ...existing defaults...
                    'core.context_processors.site_settings_processor',
                ],
            },
        }]
    """
    return {
        'SITE_NAME': 'MyApp',
        'cart_count': request.session.get('cart_count', 0) if hasattr(request, 'session') else 0,
    }


# ---------------------------------------------------------------------------
# 3c. Autoescape, |safe, XSS rules
# ---------------------------------------------------------------------------

AUTOESCAPE_RULES = """
Django template autoescaping — quick reference
===============================================

DEFAULT BEHAVIOUR (autoescape ON):
    {{ user_comment }}
    Input:  <script>alert('xss')</script>
    Output: &lt;script&gt;alert('xss')&lt;/script&gt;  ← escaped, safe

|safe FILTER — disables escaping for that variable:
    {{ user_comment|safe }}
    ☠  The script executes in the visitor's browser.
    |safe = "I personally guarantee this content is safe."

WHEN IS |safe ACCEPTABLE:
    1. Content you generated yourself (e.g., Markdown → HTML via bleach/nh3).
    2. Content sanitised through a whitelist library before storage.

NEVER:
    {{ raw_user_input|safe }}    # stored XSS → attacker owns every visitor

PYTHON SIDE — generating safe HTML:
    from django.utils.html import format_html
    format_html('<a href="{}">{}</a>', url, label)   # each arg individually escaped
    # Do NOT: mark_safe('<a href="' + url + '">' + label + '</a>')

{% autoescape off %} ... {% endautoescape %}   # block-level: almost never use
"""


# ---------------------------------------------------------------------------
# 3d. Template resolution order reference
# ---------------------------------------------------------------------------

TEMPLATE_RESOLUTION = """
TEMPLATES setting (settings.py):
---------------------------------
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],   # checked FIRST (project-level)
    'APP_DIRS': True,                   # then each app's templates/ in
}]                                      # INSTALLED_APPS order

Search order: DIRS → installed apps (in INSTALLED_APPS order)
First match wins — this has two important consequences:

  Override trick:
    To override django-allauth's login template, place your version at:
    templates/account/login.html
    It will be found before allauth's own copy.

  Collision risk (silent wrong template):
    blog/templates/list.html    collides with accounts/templates/list.html
    → whichever app comes first in INSTALLED_APPS silently wins

  SOLUTION — always namespace templates:
    blog/templates/blog/list.html       ← double-folder is intentional
    accounts/templates/accounts/list.html
"""


# ---------------------------------------------------------------------------
# 3e. Template tags reference (HTML/template syntax, non-executable)
# ---------------------------------------------------------------------------

TEMPLATE_TAG_EXAMPLES = """
Variables and filters:
    {{ post.title }}
    {{ post.created_at|date:"d M Y" }}
    {{ user.nickname|default:"Guest" }}
    {{ post.body|truncatechars:120 }}
    {{ value|lower|truncatechars:50 }}   ← chaining left-to-right

Dot-lookup order (interview question):
    dict key → attribute → method call → list index (first match wins)

Control flow:
    {% if user.is_authenticated and user.is_staff %}
        Staff panel
    {% elif user.is_authenticated %}
        Welcome {{ user.username }}
    {% else %}
        <a href="{% url 'login' %}">Login</a>
    {% endif %}

For loop with loop variables:
    {% for post in posts %}
        {{ forloop.counter }}. {{ post.title }}
        {% if forloop.first %}(latest){% endif %}
    {% empty %}
        No posts found.
    {% endfor %}

with — cache expensive lookups:
    {% with total=order.items.count %}
        {{ total }} items
        {% if total > 10 %}Bulk discount!{% endif %}
    {% endwith %}

csrf_token — required in every POST form:
    <form method="post">{% csrf_token %}...</form>

Template inheritance:
    {% extends 'base.html' %}            ← must be FIRST tag in the file
    {% block title %}Blog — {{ block.super }}{% endblock %}
    {% block content %}...{% endblock %}

Partials with explicit context (no parent context leakage):
    {% include 'blog/partials/card.html' with post=post show_author=True only %}
    ← 'only' means the partial gets ONLY the explicitly passed variables
"""


# ===========================================================================
# SECTION 4 — APP STRUCTURE & REUSABILITY
# ===========================================================================

# ---------------------------------------------------------------------------
# 4a. AppConfig — signals in ready(), not models/urls
# ---------------------------------------------------------------------------
#
# blog/apps.py
#
# from django.apps import AppConfig
#
# class BlogConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'blog'
#     verbose_name = 'Blog & Articles'    # shown in Django admin
#
#     def ready(self):
#         # Correct place to import/register signals.
#         # @receiver decorators on imported functions register automatically.
#         from . import signals  # noqa: F401
#
# Why ready() and not elsewhere:
#   models.py    → circular import risk; not the models' responsibility
#   urls.py      → not loaded during management commands → signals missed
#   ready()      → called exactly once after the app registry is fully built
#
# ready() traps:
#   1. No DB queries — schema may not exist yet (e.g. during migrate)
#   2. runserver autoreload may call ready() twice → keep it idempotent
#   3. Import signals inside ready(), not at module top-level of apps.py

READY_TRAP_NOTES = {
    'no_db_in_ready': 'Schema may not exist; migrate runs before tables exist.',
    'idempotent':     'runserver autoreloader can call ready() twice; safe to re-run.',
    'import_inside':  'Import signals inside def ready(), not at module level of apps.py.',
}


# ---------------------------------------------------------------------------
# 4b. Fat model vs services.py — the architectural decision
# ---------------------------------------------------------------------------

class _OrderModelExample:
    """
    Illustrates the FAT MODEL approach — logic lives on the model when it
    touches only that model's own data.
    """

    status: str = 'pending'
    payment_ref: str = ''

    def mark_paid_fat_model(self, payment_ref: str) -> None:
        """
        Works fine for status + ref update.
        Starts to smell when email/Celery/inventory are added here — the model
        acquires dependencies on external systems, making it hard to test.
        """
        self.status = 'paid'
        self.payment_ref = payment_ref
        # self.save(update_fields=['status', 'payment_ref'])
        # send_receipt_email.delay(self.pk)  ← hmm, email logic in a model?


def mark_order_paid(*, order: '_OrderModelExample', payment_ref: str) -> '_OrderModelExample':
    """
    SERVICES approach — a plain function in services.py.

    Keyword-only arguments (PEP 3102 *) ensure call sites are readable:
        mark_order_paid(order=order, payment_ref=ref)   ← unambiguous
        mark_order_paid(order, ref)                     ← rejected by Python

    Use when:
      - Logic touches multiple models.
      - External systems (payment gateway, email, Celery) are involved.
      - You need to call the same operation from a view AND a management
        command AND a Celery task — a model method cannot be easily imported
        without pulling in the entire ORM.

    Views stay thin: validate → call service → return response.
    Business logic in services = reusable, independently testable.
    """
    order.status = 'paid'
    order.payment_ref = payment_ref
    # order.save(update_fields=['status', 'payment_ref'])
    # send_receipt_email.delay(order.pk)
    # inventory_release(order=order)   ← multi-model orchestration is natural here
    return order


# ---------------------------------------------------------------------------
# 4c. Reusable app checklist
# ---------------------------------------------------------------------------

REUSABLE_APP_CHECKLIST = {
    '1_own_urls': (
        "blog/urls.py with app_name = 'blog' — host project does only "
        "include('blog.urls'); internal URL names are namespace-protected."
    ),
    '2_namespaced_templates': (
        "blog/templates/blog/*.html — double folder prevents collision with "
        "host project templates and other apps."
    ),
    '3_namespaced_static': (
        "blog/static/blog/*.css — same reason; django.contrib.staticfiles "
        "collects them to STATIC_ROOT with the prefix intact."
    ),
    '4_swappable_settings': (
        "Use getattr(settings, 'BLOG_POSTS_PER_PAGE', 20) — host project can "
        "override; sensible defaults mean zero-config installation."
    ),
    '5_auth_user_model': (
        "author = models.ForeignKey(settings.AUTH_USER_MODEL, ...) — NEVER "
        "import User directly; breaks projects with a custom user model."
    ),
    '6_no_hardcoded_urls': (
        "Always use reverse() / {% url %} — never hardcode '/blog/42/'."
    ),
    '7_migrations_included': (
        "Ship migrations/ with the app; downstream projects run them as-is."
    ),
}


def get_posts_per_page() -> int:
    """
    Illustrates the swappable-settings pattern for reusable apps.

    In blog/conf.py:
        from django.conf import settings
        def get_posts_per_page():
            return getattr(settings, 'BLOG_POSTS_PER_PAGE', 20)

    In blog/views.py:
        from .conf import get_posts_per_page
        class PostListView(ListView):
            paginate_by = get_posts_per_page()
    """
    # Simulated — in real code: from django.conf import settings
    default = 20
    try:
        from django.conf import settings
        return getattr(settings, 'BLOG_POSTS_PER_PAGE', default)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# 4d. Settings split — base / dev / prod
# ---------------------------------------------------------------------------

SETTINGS_SPLIT_LAYOUT = """
config/
├── settings/
│   ├── __init__.py
│   ├── base.py       — INSTALLED_APPS, MIDDLEWARE, TEMPLATES, AUTH_USER_MODEL
│   ├── dev.py        — DEBUG=True, sqlite, debug_toolbar, EMAIL_BACKEND=console
│   └── prod.py       — DEBUG=False, env-driven secrets, SECURE_SSL_REDIRECT=True
├── urls.py
├── asgi.py
└── wsgi.py

dev.py:
    from .base import *
    DEBUG = True
    ALLOWED_HOSTS = ['localhost', '127.0.0.1']
    INSTALLED_APPS += ['debug_toolbar']

prod.py:
    import os
    from .base import *
    DEBUG = False
    SECRET_KEY = os.environ['DJANGO_SECRET_KEY']     # crash if missing — intentional
    ALLOWED_HOSTS = os.environ['ALLOWED_HOSTS'].split(',')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

Activation:
    export DJANGO_SETTINGS_MODULE=config.settings.prod

Why split:
  Single settings.py with if DEBUG: branches becomes a maintenance jungle and
  risks prod secrets leaking into dev (or dev shortcuts into prod).
  Split + env vars = 12-factor compliant (see file 23).
"""


# ---------------------------------------------------------------------------
# 4e. startapp anatomy reference
# ---------------------------------------------------------------------------

STARTAPP_ANATOMY = {
    '__init__.py':      'Python package marker',
    'admin.py':         'ModelAdmin registrations — admin.site.register()',
    'apps.py':          'AppConfig — metadata + ready() signal hook',
    'migrations/':      'Schema history — never delete casually',
    'models.py':        'Data layer — single source of truth for DB schema',
    'tests.py':         'Tests; large apps → tests/ package',
    'views.py':         'Request handlers — thin; delegate to services',
    # Files you add by convention (startapp does not create these):
    'urls.py':          'App-level URLconf + app_name',
    'forms.py':         'Forms / ModelForms',
    'serializers.py':   'DRF serializers',
    'services.py':      'Business logic (multi-model / external systems)',
    'managers.py':      'Custom Manager and QuerySet subclasses',
    'templatetags/':    'Custom template filters and tags',
    'templates/blog/':  'Namespaced templates — double folder is intentional',
}


# ===========================================================================
# SECTION 5 — INTERVIEW Q&A QUICK-REFERENCE
# ===========================================================================

INTERVIEW_QA = {
    'Q1_path_vs_repath': (
        "path() is the default — readable, converters do type conversion "
        "(<int:pk> delivers an int to the view; wrong format → 404 before view runs). "
        "re_path() only for legacy patterns or one-off regexes that resist "
        "converters. Pattern reused in 2+ places → write a custom converter. "
        "re_path captured groups are always str — subtle type-bug source."
    ),
    'Q2_as_view_internals': (
        "as_view() returns a plain closure (called once at startup). Per request: "
        "new class instance is created (thread-safety), setup() binds request/args/"
        "kwargs, dispatch() routes request.method to get()/post()/etc. "
        "CBV is ultimately a function; per-request fresh instance means instance "
        "state is safe, but class-level mutable attributes are shared — classic trap."
    ),
    'Q3_namespace': (
        "Two apps can both name a view 'detail'; without namespace, reverse('detail') "
        "returns whichever was registered first — silent wrong link. "
        "app_name = APPLICATION namespace (declared in app urls.py); "
        "namespace= in include() = INSTANCE namespace (same app at multiple mounts). "
        "Reverse: reverse('blog:detail', kwargs={'pk': 1})."
    ),
    'Q4_fbv_vs_cbv': (
        "CBV wins when the same pattern repeats (standard CRUD × N models — mixins + "
        "generics = reuse). FBV wins when logic is unique/branching-heavy — forcing it "
        "into CBV means 5-6 method overrides = more code. Neither is more 'advanced'. "
        "Webhooks / one-offs → FBV; 10-model CRUD dashboard → CBV."
    ),
    'Q5_mixin_order': (
        "Python MRO is left-to-right. LoginRequiredMixin.dispatch() does auth check "
        "then calls super().dispatch(). Mixin must be leftmost so its dispatch runs "
        "first; wrong order can skip the auth check entirely. "
        "Rule: mixins left, base generic view rightmost. "
        "Verify: print(MyView.__mro__)."
    ),
    'Q6_form_valid_vs_get_queryset': (
        "get_queryset() — read-time scope: filtering, select_related, per-user "
        "security (UpdateView/DeleteView get_object() pulls from this queryset). "
        "form_valid(form) — write-time injection: set form.instance.author before save, "
        "or trigger side effects (Celery, email). Always call super().form_valid(form) — "
        "it does the actual save + redirect."
    ),
    'Q7_autoescape_and_safe': (
        "Django escapes < > & \" ' by default — XSS protection is on. "
        "|safe disables escaping; user-generated content + |safe = stored XSS. "
        "Only use |safe on content you generated or sanitised (bleach/nh3 whitelist). "
        "Python side: format_html() escapes each argument; avoid mark_safe() + concat."
    ),
    'Q8_template_resolution': (
        "DIRS (project-level) checked first, then APP_DIRS (each app's templates/ "
        "in INSTALLED_APPS order). First match wins. "
        "Override third-party templates by placing yours in project-level templates/ "
        "at the same relative path. "
        "Prevent collisions: always namespace — app/templates/app/file.html."
    ),
    'Q9_signals_ready': (
        "Register signals in AppConfig.ready() via 'from . import signals'. "
        "models.py → circular import risk; urls.py → not loaded by management "
        "commands. ready() runs after app registry is complete. "
        "Traps: no DB queries in ready(); keep it idempotent (runserver double-calls)."
    ),
    'Q10_fat_vs_services': (
        "Single-model own-data logic → model methods/properties (Django philosophy). "
        "Multi-model orchestration or external systems → services.py plain functions "
        "with keyword-only args. Business logic in views = not reusable from "
        "Celery/management commands. Pragmatic mix is fine; avoid dogma."
    ),
}


# ===========================================================================
# SECTION 6 — STANDALONE DEMO (runs without Django project)
# ===========================================================================

def _demo_year_month_converter() -> None:
    """Demonstrate the custom YearMonthConverter round-trip."""
    converter = YearMonthConverter()

    # to_python: URL string → Python date
    date_obj = converter.to_python('2024-06')
    assert date_obj == datetime.date(2024, 6, 1), f"Unexpected: {date_obj}"

    # to_url: Python date → URL string (for reverse())
    url_str = converter.to_url(date_obj)
    assert url_str == '2024-06', f"Unexpected: {url_str}"

    print(f"  YearMonthConverter: '2024-06' → {date_obj!r} → '{url_str}'")


def _demo_rupees_filter() -> None:
    """Demonstrate the Indian-style currency filter."""
    cases = [
        (0,        '₹0'),
        (100,      '₹100'),
        (1000,     '₹1,000'),
        (12345,    '₹12,345'),
        (1234567,  '₹12,34,567'),
        (10000000, '₹1,00,00,000'),
    ]
    for value, expected in cases:
        result = rupees(value)
        assert result == expected, f"rupees({value}) = {result!r}, expected {expected!r}"
        print(f"  rupees({value:>10,}) = {result}")


def _demo_startswith_filter() -> None:
    """Demonstrate the startswith template filter."""
    assert startswith_filter('admin_user', 'admin') is True
    assert startswith_filter('guest', 'admin') is False
    print('  startswith_filter: OK')


def _demo_current_year() -> None:
    """Demonstrate the simple_tag returning the current year."""
    year = current_year()
    assert year == datetime.date.today().year
    print(f'  current_year() = {year}')


def _demo_mro_print() -> None:
    """
    Illustrate MRO resolution for the OwnerOnlyMixin without needing Django.

    In a real project:
        class PostUpdateView(OwnerOnlyMixin, LoginRequiredMixin, UpdateView): ...
        print(PostUpdateView.__mro__)

    Here we use our lightweight _ViewBase to show the pattern.
    """

    class MockLoginMixin(_ViewBase):
        def dispatch(self, request, *args, **kwargs):
            # Simulated auth check
            if not getattr(request, 'user_authenticated', False):
                return 'REDIRECT_TO_LOGIN'
            return super().dispatch(request, *args, **kwargs)

    class MockView(MockLoginMixin, _ViewBase):
        def get(self, request, *args, **kwargs):
            return 'VIEW_RESPONSE'

    mro_names = [cls.__name__ for cls in MockView.__mro__]
    print(f'  MRO: {" → ".join(mro_names)}')
    assert mro_names.index('MockLoginMixin') < mro_names.index('_ViewBase'), \
        "Mixin must appear before base view in MRO"


def _demo_services_pattern() -> None:
    """Demonstrate the services pattern with keyword-only arguments."""
    order = _OrderModelExample()
    order.status = 'pending'

    result = mark_order_paid(order=order, payment_ref='PAY-001')
    assert result.status == 'paid'
    assert result.payment_ref == 'PAY-001'
    print(f'  mark_order_paid: status={result.status!r}, ref={result.payment_ref!r}')


def _demo_get_posts_per_page() -> None:
    """Demonstrate the swappable settings helper."""
    ppp = get_posts_per_page()
    assert isinstance(ppp, int) and ppp > 0
    print(f'  get_posts_per_page() = {ppp}')


def _demo_reusable_checklist() -> None:
    """Print the reusable app checklist."""
    print('\n  Reusable App Checklist:')
    for key, description in REUSABLE_APP_CHECKLIST.items():
        print(f'    [{key}] {description[:80]}...')


if __name__ == '__main__':
    print('\n' + '=' * 70)
    print('  Django URLs / Views / Templates / Apps — Deep Dive Demo')
    print('=' * 70 + '\n')

    print('[1] Custom URL converter (YearMonthConverter)')
    _demo_year_month_converter()

    print('\n[2] Custom template filter — rupees (Indian number format)')
    _demo_rupees_filter()

    print('\n[3] Custom template filter — startswith')
    _demo_startswith_filter()

    print('\n[4] Custom simple_tag — current_year')
    _demo_current_year()

    print('\n[5] Mixin MRO ordering verification')
    _demo_mro_print()

    print('\n[6] Services pattern — mark_order_paid()')
    _demo_services_pattern()

    print('\n[7] Swappable settings helper — get_posts_per_page()')
    _demo_get_posts_per_page()

    print('\n[8] Reusable app checklist')
    _demo_reusable_checklist()

    print('\n[9] Interview Q&A quick-reference (keys):')
    for key in INTERVIEW_QA:
        print(f'    {key}')

    print('\n' + '=' * 70)
    print('  All assertions passed. Module is syntactically valid.')
    print('=' * 70 + '\n')
