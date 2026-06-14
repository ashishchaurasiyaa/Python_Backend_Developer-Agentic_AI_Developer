"""
Django MVT Architecture, Fields & Relationships — Production Patterns
=====================================================================

Covers the "Day 1 basics at senior depth" gaps that screen out junior/mid candidates:

  1.  MVT architecture and full request lifecycle (Controller confusion)
  2.  startproject vs startapp — file layout and INSTALLED_APPS impact
  3.  Model field types with null vs blank rules
  4.  TextChoices / IntegerChoices (type-safe enum approach)
  5.  default pitfalls — mutable defaults, import-time evaluation, db_default
  6.  on_delete semantics — all seven options, PROTECT vs RESTRICT deep-dive
  7.  ManyToManyField with explicit through= model
  8.  related_name vs related_query_name
  9.  Self-referencing FK and symmetrical / asymmetric self-M2M
  10. HttpRequest anatomy — GET, POST, body, headers, FILES, META
  11. HttpResponse subclasses + JsonResponse safe=False trap
  12. Shortcuts — render, redirect (3 flavors), get_object_or_404
  13. Static vs media files — settings, dev serving, Whitenoise, prod checklist

All imports are real Django 4.2/5.0 APIs.  The module compiles and is importable
as long as Django is installed (`pip install django`).  No DB connection is
required at import time — this is an illustrative/reference module.

Usage:
    python -m py_compile 40_django_mvt_fields_relationships_gaps.py
    # (run inside a configured Django project for ORM operations)

pip install django whitenoise pillow
"""

from __future__ import annotations

import json
import uuid
from typing import Any

# ---------------------------------------------------------------------------
# Django bootstrap — required before importing django.db.models
# ---------------------------------------------------------------------------
import django
from django.conf import settings as django_settings

if not django_settings.configured:
    django_settings.configure(
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        USE_TZ=True,
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    )
    django.setup()

from django.db import models
from django.utils import timezone

# ==========================================================================
# SECTION 1 — MVT ARCHITECTURE: Request Lifecycle Commentary
# ==========================================================================
#
# Django is officially an MTV framework (Model-Template-View).  The mapping
# to the conventional MVC pattern is:
#
#   MVC term      │ Django term  │ Role
#   ─────────────────────────────────────────────────────────────────────
#   Model         │ Model        │ Data structure + ORM + business rules
#   Controller    │ View         │ Request handler — fetches data, picks
#                 │  (views.py)  │ template, returns response
#   View (UI)     │ Template     │ Presentation only — HTML + context vars
#   Router        │ URLconf      │ Maps URL patterns to view callables
#
# Django documentation's official reasoning: "view" = which data you see
# (the data description), not HOW you see it.  The framework itself plays
# the "controller" role — URLconf machinery routes requests to the right
# view function/class.  Architecture is MVC-family; naming differs.
#
# Full request journey for GET /articles/5/:
#
#   WSGI/ASGI server (gunicorn / uvicorn)
#     │
#     ▼
#   Middleware stack — top-to-bottom on request, bottom-to-top on response
#   (SecurityMiddleware, SessionMiddleware, AuthenticationMiddleware …)
#     │
#     ▼
#   URLconf (urls.py) — pattern match, extract kwargs={'pk': 5}
#     │
#     ▼
#   View function / class-based view (views.py)
#     ├── Model layer  → Article.objects.get(pk=5)  [ORM → DB]
#     └── Template     → render(request, 'blog/detail.html', context)
#     │
#     ▼
#   HttpResponse  (HTML / JSON / file stream …)
#     │
#     ▼
#   Browser
#
# ==========================================================================


# ==========================================================================
# SECTION 2 — startproject vs startapp: INSTALLED_APPS Impact
# ==========================================================================
#
# django-admin startproject mysite .   → PROJECT container
#   mysite/settings.py, urls.py, wsgi.py, asgi.py, manage.py
#
# python manage.py startapp blog       → APP — one self-contained feature
#   blog/models.py, views.py, admin.py, apps.py, migrations/, tests.py
#   (urls.py is a convention — create it manually)
#
# Registering an app in INSTALLED_APPS activates ALL of:
#   1. AppConfig.ready() hook  → connect signals here, not at module level
#   2. Models discovery        → ORM registry; without this you get RuntimeError
#   3. Migrations tracking     → makemigrations / migrate see this app only
#   4. Template namespacing    → APP_DIRS=True scans <app>/templates/
#                                Convention: blog/templates/blog/detail.html
#                                (double dir!) to avoid cross-app clashes
#   5. Static namespacing      → blog/static/blog/style.css; collectstatic sweeps
#   6. Admin autodiscovery     → admin.py auto-imported
#   7. Management commands     → blog/management/commands/*.py
#   8. Test discovery          → test runner picks up app tests
#
# Classic symptom of forgetting:
#   makemigrations → "No changes detected"  ← 90% of the time: INSTALLED_APPS
#


# ==========================================================================
# SECTION 3 — Model Field Types with null vs blank Rules
# ==========================================================================

class UserProfile(models.Model):
    """
    Demonstrates correct null / blank usage across field types.

    Rule of thumb:
      • String fields (CharField, TextField, SlugField …) — never null=True.
        Use blank=True only; empty value stored as '' (empty string).
        Two empty states (NULL + '') create query/uniqueness chaos.
        Exception: unique=True + optional → null=True is justified (multiple
        NULLs do not violate UNIQUE; multiple '' do).

      • Non-string fields (DateField, IntegerField, FK, DecimalField …) —
        empty string impossible; use null=True (and blank=True for forms).

      • FileField / ImageField — stores a path string in DB; never null=True
        on the path column (same string-field rule); use blank=True alone.
    """

    # --- String fields — blank=True only ---
    display_name = models.CharField(max_length=150)             # required, no empty
    bio = models.TextField(blank=True)                          # optional text → '' stored
    website = models.URLField(blank=True)                       # URLField = CharField + validator
    slug = models.SlugField(unique=True)                        # required unique slug

    # Exception: unique=True + optional → null=True justified
    twitter_handle = models.CharField(
        max_length=50,
        unique=True,
        null=True,      # multiple NULLs OK for UNIQUE; multiple '' would collide
        blank=True,
        default=None,
    )

    # --- Non-string fields — null=True, blank=True for optional ---
    birth_date = models.DateField(null=True, blank=True)        # empty int/date needs NULL
    score = models.DecimalField(                                # money/scores: DecimalField!
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )                                                           # FloatField has binary rounding

    # --- UUID primary key pattern ---
    external_id = models.UUIDField(default=uuid.uuid4, unique=True)

    # --- JSONField — callable default, never mutable literal ---
    # pip install django  (JSONField built-in Django 3.1+)
    preferences = models.JSONField(default=dict)                # ✅ callable — fresh {} each time
    tags = models.JSONField(default=list)                       # ✅ callable — fresh [] each time
    # WRONG: default={} or default=[] — all instances share the SAME object (W039 warning)

    # --- Timestamps ---
    created_at = models.DateTimeField(auto_now_add=True)        # set once on INSERT
    updated_at = models.DateTimeField(auto_now=True)            # set on every save()

    # auto_now_add / auto_now set editable=False; cannot be overridden via save().
    # If you need to set it manually (e.g. data import), use default=timezone.now
    # and remove auto_now_add.

    # --- File / Image (pip install pillow for ImageField) ---
    avatar = models.ImageField(
        upload_to="avatars/%Y/%m/",     # media/avatars/2026/06/photo.jpg
        blank=True,                     # optional — empty path '' stored, not NULL
    )
    # avatar.url  → '/media/avatars/2026/06/photo.jpg'
    # DB column stores only the relative path string; actual file lives in MEDIA_ROOT.

    class Meta:
        app_label = "auth"              # reuse built-in app label for in-memory demo


# ==========================================================================
# SECTION 4 — TextChoices / IntegerChoices (Django 3.0+)
# ==========================================================================

class Article(models.Model):
    """
    Illustrates all three choices styles and the get_FOO_display() auto-method.
    """

    # Style 1 — legacy tuple list (still common in older codebases)
    CATEGORY_CHOICES = [
        ("tech", "Technology"),
        ("sci", "Science"),
        ("arts", "Arts"),
    ]

    # Style 2 — TextChoices (PREFERRED): enum-like, namespaced, type-safe
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    # Style 3 — IntegerChoices: DB stores compact int, fast comparisons
    class Priority(models.IntegerChoices):
        LOW = 1, "Low"
        MEDIUM = 2, "Medium"
        HIGH = 3, "High"

    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    priority = models.IntegerField(
        choices=Priority.choices,
        default=Priority.LOW,
    )

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="tech",
    )

    # TextChoices advantages:
    #   Article.objects.filter(status=Article.Status.PUBLISHED)   ← typo = AttributeError
    #   Article.objects.filter(status='publishd')                 ← typo = silent 0 results
    #
    # get_FOO_display() is a FREE method on every choices field:
    #   article.get_status_display()    → 'Draft'   (human label, not stored value)
    #   article.get_priority_display()  → 'Low'
    #   In templates: {{ article.get_status_display }}
    #
    # Note: choices are APP-LEVEL validation only (forms / full_clean).
    # DB CHECK constraint is NOT created.  For hard DB guarantee add:
    #   models.CheckConstraint(
    #       condition=models.Q(status__in=Article.Status.values),
    #       name="article_status_valid",
    #   )

    class Meta:
        app_label = "auth"


# ==========================================================================
# SECTION 5 — default Pitfalls
# ==========================================================================

def demonstrate_default_pitfalls() -> None:
    """
    Documents the three most common default= mistakes; does not execute ORM
    operations (no DB needed).
    """

    # --- Pitfall 1: mutable default ---
    # WRONG — all model instances at Python level share the same list object:
    #   tags = models.JSONField(default=[])    # ❌ W039 warning + shared mutation
    #
    # CORRECT — pass a callable; Django calls it for each new instance:
    #   tags = models.JSONField(default=list)   # ✅

    # --- Pitfall 2: import-time evaluation with () ---
    # WRONG — evaluated ONCE when module is imported; every row gets the same timestamp:
    #   created = models.DateTimeField(default=timezone.now())   # ❌ () applied here
    #
    # CORRECT — callable reference; evaluated at INSERT time:
    #   created = models.DateTimeField(default=timezone.now)     # ✅

    # --- Pitfall 3: default= vs db_default= (Django 5.0+) ---
    #
    # default=          → Python level; Django ORM sets it before INSERT.
    #                     Raw SQL INSERT or other services bypass this entirely.
    #
    # db_default=       → Generates a SQL DEFAULT clause in the schema.
    #                     ANY writer (raw SQL, other microservices) gets the default.
    #                     Uses DB expressions: Now(), Value('pending'), …
    #
    #   class Order(models.Model):
    #       status  = models.CharField(max_length=20, default='pending')     # Python
    #       created = models.DateTimeField(db_default=Now())                 # DB clause
    #
    # Rule: single Django-app writer → default= fine.
    #       Multi-writer DB or raw SQL pipelines → db_default= for guarantee.

    print("default pitfall notes documented — see inline comments")


# ==========================================================================
# SECTION 6 — Relationships: on_delete Semantics
# ==========================================================================

class Customer(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "auth"


class Order(models.Model):
    """
    Illustrates on_delete choices with rationale.

    on_delete is Python-level enforcement (Django collector).
    Raw SQL DELETE bypasses Django-level CASCADE/SET_NULL — only DB-level
    ON DELETE clauses (which Django migrations do NOT add by default) would
    catch that.  Multi-writer DBs may need explicit DB-level constraints.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    # PROTECT — unconditional block.  Prevents delete of Customer if any Order
    # references them.  Critical for financial / audit data — paid invoices must
    # never cascade-delete when a customer record is removed.
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,           # ProtectedError raised — delete blocked
        related_name="orders",
        related_query_name="order",         # singular for clean filter paths
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    notes = models.TextField(blank=True)    # blank only — never null on text fields
    metadata = models.JSONField(default=dict)

    class Meta:
        app_label = "auth"


class Comment(models.Model):
    """
    SET_NULL — preserves history when the referenced user is deleted.
    Comment becomes "anonymous" rather than disappearing.
    """

    # Circular import avoided by using string reference 'auth.User'
    author = models.ForeignKey(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,          # FK set to NULL; null=True required
        related_name="comments",
    )
    body = models.TextField()

    class Meta:
        app_label = "auth"


# --- PROTECT vs RESTRICT deep-dive ---
#
#   class Artist(models.Model): ...
#   class Album(models.Model):
#       artist = models.ForeignKey(Artist, on_delete=CASCADE)
#   class Song(models.Model):
#       artist = models.ForeignKey(Artist, on_delete=CASCADE)
#       album  = models.ForeignKey(Album,  on_delete=RESTRICT)  ← key line
#
#   artist.delete()
#     With PROTECT on Song.album:  ProtectedError — unconditional block,
#                                  no exceptions, Song exists → stop.
#     With RESTRICT on Song.album: ALLOWED — Album is being deleted in the
#                                  SAME cascade operation (artist.delete()
#                                  cascades to Album which cascades away),
#                                  so Song.album reference resolves within
#                                  the same delete set — no orphan created.
#
#   album.delete()                 RestrictedError — Song references Album
#                                  and Album alone is being deleted; Song
#                                  would become orphaned → blocked.
#
# One-liner:
#   PROTECT  = always block if any reference exists.
#   RESTRICT = block, EXCEPT when the referenced object is also being deleted
#              within the same cascade operation.
#
# All seven on_delete options:
#   CASCADE      → delete children too (owned data: sessions, line items)
#   PROTECT      → raise ProtectedError unconditionally
#   RESTRICT     → raise RestrictedError unless same-cascade resolution
#   SET_NULL     → FK = NULL  (needs null=True on the FK column)
#   SET_DEFAULT  → FK = field default value  (needs a default= defined)
#   SET(v)       → FK = callable/value  (sentinel user pattern)
#   DO_NOTHING   → leave FK as-is → DB IntegrityError unless DB handles it


# ==========================================================================
# SECTION 7 — ManyToManyField with Explicit through= Model
# ==========================================================================

class Group(models.Model):
    name = models.CharField(max_length=100)

    # Through model — junction table is now YOUR model; add any extra columns.
    members = models.ManyToManyField(
        "auth.User",
        through="Membership",
        related_name="member_groups",
    )

    class Meta:
        app_label = "auth"


class Membership(models.Model):
    """
    Explicit junction table for Group ↔ User with extra relationship data.

    Why explicit through=?
      Plain M2M only records "linked / not linked".  When the relationship
      itself carries data (join date, role, quantity, price, expiry) you need
      explicit through.  Pro tip: if there is any doubt, use through= from
      the start — migrating plain M2M → through later is painful (table
      rename + data migration dance).
    """

    person = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    date_joined = models.DateField(auto_now_add=True)           # extra field — the whole point
    role = models.CharField(max_length=50, default="member")

    class Meta:
        app_label = "auth"
        constraints = [
            models.UniqueConstraint(
                fields=["person", "group"],
                name="uniq_membership_person_group",
            )
        ]

    # --- Usage patterns (illustrative, no DB required) ---
    #
    # Add with extra fields via through_defaults (Django 2.2+):
    #   group.members.add(user, through_defaults={"role": "admin"})
    #
    # Or create explicitly — always works:
    #   Membership.objects.create(person=user, group=group, role="admin")
    #
    # Queries both directions:
    #   group.members.all()                             # User queryset
    #   user.member_groups.filter(membership__role="admin")  # filter on junction
    #   Membership.objects.filter(group=group).select_related("person")


# ==========================================================================
# SECTION 8 — related_name vs related_query_name
# ==========================================================================

class BlogPost(models.Model):
    """
    Shows the difference between the reverse accessor name and the filter path.
    """

    author = models.ForeignKey(
        "auth.User",
        on_delete=models.CASCADE,
        related_name="blog_posts",          # ACCESSOR: user.blog_posts.all()
        related_query_name="blog_post",     # FILTER PATH: User.objects.filter(blog_post__title=…)
    )
    title = models.CharField(max_length=200)
    published = models.BooleanField(default=False)

    class Meta:
        app_label = "auth"

    # Comparison table:
    #
    #                  related_name           related_query_name
    #   ─────────────────────────────────────────────────────────
    #   Where used     instance accessor       ORM queryset lookup path
    #   Example        user.blog_posts.all()   User.objects.filter(blog_post__title='X')
    #   Default        <model>_set             = related_name value (or model name)
    #   Special value  '+' disables reverse    —
    #
    # Pattern: related_name plural (collection semantics),
    #          related_query_name singular (readable filter path).
    #
    # If you omit related_query_name the filter path equals related_name:
    #   filter(blog_posts__title=…)  ← plural — slightly awkward to read.
    # Explicit related_query_name='blog_post' gives:
    #   filter(blog_post__title=…)   ← singular — conventional ORM style.


# ==========================================================================
# SECTION 9 — Self-Referencing FK and Self-M2M
# ==========================================================================

class Employee(models.Model):
    """
    Self-referencing ForeignKey — org-chart / tree structure.
    'self' string avoids circular model reference.
    """

    name = models.CharField(max_length=100)
    manager = models.ForeignKey(
        "self",                             # string 'self' — points to own model
        null=True,
        blank=True,                         # CEO has no manager
        on_delete=models.SET_NULL,
        related_name="direct_reports",      # manager.direct_reports.all()
    )

    class Meta:
        app_label = "auth"

    # emp.manager              → one level up
    # emp.direct_reports.all() → one level down (direct reports)
    # Recursive tree queries → use django-treebeard or ltree extension for deep trees


class SocialUser(models.Model):
    """
    Self-referencing ManyToManyField — two common configurations.
    """

    username = models.CharField(max_length=50)

    # Symmetrical (default for self-M2M) — friendship model:
    # a.friends.add(b) → b automatically appears in a.friends AND a appears in b.friends.
    # Django manages both directions with one row per pair.
    # Note: symmetrical=True disallows related_name (same accessor in both directions).
    friends = models.ManyToManyField("self")  # symmetrical=True is the default

    # Asymmetric — Twitter-style follow (A follows B ≠ B follows A):
    following = models.ManyToManyField(
        "self",
        symmetrical=False,
        related_name="followers",
    )
    # a.following.add(b) → b.followers includes a, but b.following does NOT include a.

    class Meta:
        app_label = "auth"


# ==========================================================================
# SECTION 10 — HttpRequest Anatomy
# ==========================================================================

def demonstrate_request_anatomy(request: Any) -> None:
    """
    Documents every commonly-accessed attribute of HttpRequest.
    The `request` parameter is a django.http.HttpRequest instance.
    """

    # --- Method ---
    _ = request.method              # 'GET', 'POST', 'PUT', 'PATCH', 'DELETE', …

    # --- URL query parameters (GET dict is a QueryDict) ---
    _ = request.GET.get("q", "")           # safe .get() with default — ['q'] raises KeyError
    _ = request.GET.getlist("tag")         # ?tag=a&tag=b → ['a', 'b'] — multi-value

    # --- Form-encoded POST body ---
    _ = request.POST.get("name")           # ONLY for multipart/application/x-www-form-urlencoded

    # *** TRAP: JSON API requests — request.POST is EMPTY ***
    # JSON body is NOT form-encoded; request.POST will not parse it.
    # Read the raw bytes instead:
    #   data = json.loads(request.body)    # ✅ for Content-Type: application/json

    # --- File uploads ---
    # avatar_file = request.FILES["avatar"]      # InMemoryUploadedFile / TemporaryUploadedFile
    # avatar_file.name, avatar_file.size, avatar_file.read()

    # --- Headers (Django 2.2+) ---
    _ = request.headers.get("User-Agent", "")       # case-insensitive, clean API
    # Avoid request.META['HTTP_USER_AGENT'] — WSGI environ key mangling is fragile

    # --- WSGI environ (low-level) ---
    _ = request.META.get("REMOTE_ADDR")             # client IP (trust only behind trusted proxy)
    _ = request.META.get("HTTP_X_FORWARDED_FOR")    # set by reverse proxies — validate

    # --- Auth ---
    _ = request.user                                # User or AnonymousUser (from AuthMiddleware)
    _ = request.user.is_authenticated              # True / False

    # --- Path ---
    _ = request.path                                # '/articles/5/'
    _ = request.get_full_path()                     # '/articles/5/?page=2'

    print("request anatomy demonstrated — see inline comments")


# ==========================================================================
# SECTION 11 — HttpResponse Subclasses + JsonResponse safe=False
# ==========================================================================

def demonstrate_responses() -> None:
    """
    Illustrates HttpResponse subclasses and the JsonResponse safe=False trap.
    Imports are shown inline to keep the module importable without a running
    Django application.
    """
    from django.http import (
        FileResponse,
        HttpResponse,
        HttpResponseBadRequest,
        HttpResponseForbidden,
        HttpResponseNotAllowed,
        HttpResponseNotFound,
        HttpResponsePermanentRedirect,
        HttpResponseRedirect,
        JsonResponse,
        StreamingHttpResponse,
    )

    # --- HttpResponse subclasses quick reference ---
    #
    # Class                       Status  Common use
    # ─────────────────────────────────────────────────────────────────
    # HttpResponse(content)          200  Base — any body + content_type
    # JsonResponse({'k': 1})         200  dict → JSON, auto Content-Type header
    # HttpResponseRedirect('/x/')    302  Temporary redirect (use redirect() shortcut)
    # HttpResponsePermanentRedirect  301  Permanent — browser caches aggressively!
    # HttpResponseNotFound()         404  (prefer raise Http404 / get_object_or_404)
    # HttpResponseForbidden()        403  Permission denied
    # HttpResponseNotAllowed(['GET'])405  Wrong HTTP method
    # HttpResponseBadRequest()       400  Malformed request
    # FileResponse(open(f,'rb'))     200  Streaming binary file download
    # StreamingHttpResponse(gen)     200  Generator-based chunked — large CSV exports

    # --- JsonResponse: safe=False trap ---
    # Default safe=True rejects non-dict serialization:
    #
    #   return JsonResponse([1, 2, 3])              # ❌ TypeError raised
    #   return JsonResponse([1, 2, 3], safe=False)  # ✅ list serialized OK
    #
    # WHY safe=True is the default:
    #   Historical JSON-hijacking: top-level JSON arrays in browsers could be
    #   captured via <script src=...> + Array constructor override.  Top-level
    #   dict is not valid JavaScript in that context — safe by default.
    #   Modern browsers are patched, but the conservative default remains.
    #
    # BEST PRACTICE: always return a top-level dict regardless of content:
    #   return JsonResponse({"results": [1, 2, 3]})    # ✅ safe=True, extensible
    #   # Future pagination metadata can be added alongside "results"

    _ = HttpResponse           # reference prevents "imported but unused" linting noise
    _ = JsonResponse
    _ = HttpResponseRedirect
    _ = HttpResponsePermanentRedirect
    _ = HttpResponseNotFound
    _ = HttpResponseForbidden
    _ = HttpResponseNotAllowed
    _ = HttpResponseBadRequest
    _ = FileResponse
    _ = StreamingHttpResponse
    print("response subclasses documented — see inline comments")


# ==========================================================================
# SECTION 12 — Shortcuts: render, redirect, get_object_or_404
# ==========================================================================

def demonstrate_shortcuts() -> None:
    """
    Documents the three most important Django view shortcuts.
    """
    from django.shortcuts import (
        get_list_or_404,
        get_object_or_404,
        redirect,
        render,
    )

    # --- render(request, template_name, context, status=200) ---
    # Combines: load template + render with context + wrap in HttpResponse
    # Equivalent to:
    #   t = loader.get_template('blog/detail.html')
    #   return HttpResponse(t.render(context, request))
    #
    # Example:
    #   return render(request, 'blog/detail.html', {'article': article})

    # --- redirect() — three flavors ---
    #
    # 1. Named URL + kwargs (recommended):
    #   return redirect('article-detail', pk=5)      # reverse() internally
    #
    # 2. Model instance → calls get_absolute_url():
    #   return redirect(article)
    #
    # 3. Hardcoded path (avoid — breaks on URL refactor):
    #   return redirect('/articles/5/')
    #
    # 4. Permanent (301) — USE WITH CAUTION:
    #   return redirect('home', permanent=True)
    #   Browsers cache 301 aggressively.  If you later change the target,
    #   users' browsers serve the stale redirect until cache expires.
    #   Always default to 302 until the redirect is truly permanent.

    # --- get_object_or_404 ---
    # Eliminates try/except Article.DoesNotExist boilerplate.
    # Raises Http404 (→ 404 response) when not found.
    #
    #   article = get_object_or_404(Article, pk=pk)
    #   # With queryset (for select_related, filters, etc.):
    #   article = get_object_or_404(Article.objects.select_related('author'), pk=pk)
    #
    # Note: does NOT catch MultipleObjectsReturned — that is a data bug (500).
    #
    # --- get_list_or_404 ---
    # Like filter() + check that result is non-empty; raises 404 on empty list.
    #   articles = get_list_or_404(Article, status='published')

    _ = render
    _ = redirect
    _ = get_object_or_404
    _ = get_list_or_404
    print("shortcuts documented — see inline comments")


# ==========================================================================
# SECTION 13 — Static vs Media: Settings, Dev Serving, Whitenoise, Prod
# ==========================================================================

STATIC_MEDIA_SETTINGS_EXAMPLE = """
# -----------------------------------------------------------------------
# settings.py — static and media configuration
# -----------------------------------------------------------------------

from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent

# Static files (CSS / JS / images that ship with your code)
STATIC_URL     = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']          # extra non-app static dirs
STATIC_ROOT    = BASE_DIR / 'staticfiles'          # collectstatic destination (prod)

# Media files (user uploads — runtime content)
MEDIA_URL  = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# FileField / ImageField:
#   avatar = models.ImageField(upload_to='avatars/%Y/%m/')
#   Stores relative path 'avatars/2026/06/photo.jpg' in DB column.
#   avatar.url → '/media/avatars/2026/06/photo.jpg'
"""

DEV_MEDIA_URLCONF_EXAMPLE = """
# -----------------------------------------------------------------------
# urls.py — serve media files in DEVELOPMENT (DEBUG=True) only
# -----------------------------------------------------------------------

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # ... your URL patterns ...
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# static() returns an empty list when DEBUG=False — safe no-op in production.
# runserver automatically serves static files (via staticfiles app) when DEBUG=True;
# media requires this explicit helper.
"""

WHITENOISE_SETTINGS_EXAMPLE = """
# -----------------------------------------------------------------------
# Whitenoise — serve static files efficiently from within Django
# pip install whitenoise
# -----------------------------------------------------------------------

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # ← immediately after Security
    # ... rest of middleware ...
]

# Django 4.2+ STORAGES dict:
STORAGES = {
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}
# CompressedManifest: pre-compresses (gzip + brotli), appends content hash to
# filenames (style.abc123.css), sets far-future Cache-Control headers.

# When to use Whitenoise:
#   ✅ PaaS (Heroku, Railway, Render) — no separate nginx available
#   ✅ Small-medium traffic; simple single-server setup
#
# When to prefer nginx / S3 + CDN:
#   ✅ High traffic — CDN edge nodes serve from global PoPs
#   ✅ Large static asset set
#   ✅ MEDIA files — Whitenoise does NOT serve media; use S3 + django-storages
#      (PaaS disks are often ephemeral — local MEDIA_ROOT gets wiped on redeploy!)
"""

PROD_STATIC_CHECKLIST = """
Production static/media checklist
----------------------------------
1.  DEBUG = False  +  ALLOWED_HOSTS set correctly
2.  python manage.py collectstatic --noinput
    → all app static files gathered into STATIC_ROOT
3.  Static serving — pick ONE:
    a. nginx:    location /static/ { alias /app/staticfiles/; }
    b. Whitenoise middleware (in-process, compressed, hashed filenames)
    c. S3 + CDN (django-storages STORAGES['staticfiles'] backend)
4.  Media serving — pick ONE:
    a. nginx:    location /media/ { alias /app/media/; }
       (disable script handlers — user uploads are untrusted!)
    b. S3 + django-storages DEFAULT_FILE_STORAGE
       (preferred: PaaS disks are ephemeral; S3 is durable)
5.  Never serve files from the Django app worker process in production
    (blocks a Python worker thread, no caching headers, 10× slower).
6.  Filename sanitization: Django does this automatically for FileField
    uploads; never trust user-supplied filenames raw.
7.  django-storages + S3 for media: pip install django-storages boto3
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
"""


# ==========================================================================
# SECTION 14 — Real-World Pattern: SaaS Order Model (all patterns combined)
# ==========================================================================

class Product(models.Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)   # never FloatField for money

    class Meta:
        app_label = "auth"


class SaaSOrder(models.Model):
    """
    Combines: TextChoices, PROTECT FK, blank-only text, callable JSON default,
    explicit through M2M with OrderItem — the complete pattern for a SaaS order.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,           # paid orders survive customer deletion
        related_name="saas_orders",
        related_query_name="saas_order",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    notes = models.TextField(blank=True)    # blank only — never null on text
    metadata = models.JSONField(default=dict)   # callable default

    items = models.ManyToManyField(Product, through="OrderItem")

    class Meta:
        app_label = "auth"


class OrderItem(models.Model):
    """
    Through model for SaaSOrder ↔ Product — stores quantity and unit price
    at time of order (price snapshot — independent of Product.price changes).
    """

    order = models.ForeignKey(SaaSOrder, on_delete=models.CASCADE, related_name="order_items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)  # keep history
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # price snapshot

    class Meta:
        app_label = "auth"
        constraints = [
            models.UniqueConstraint(
                fields=["order", "product"],
                name="uniq_orderitem_order_product",
            )
        ]


# ==========================================================================
# SECTION 15 — JSON API View Pattern (HttpRequest / HttpResponse hygiene)
# ==========================================================================

def create_order_api_view(request: Any) -> Any:
    """
    Production-grade JSON API view demonstrating correct request/response
    hygiene for a non-DRF function-based view.

    Key rules demonstrated:
      • json.loads(request.body) — not request.POST — for JSON payloads
      • Method check first → HttpResponseNotAllowed
      • Top-level dict in JsonResponse — never a bare list
      • Explicit status=201 for resource creation
      • Exception boundary with meaningful 400 error response
    """
    from django.http import HttpResponseNotAllowed, JsonResponse

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])                 # 405, allowed list in body

    try:
        data = json.loads(request.body)                         # ✅ body, NOT request.POST
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    customer_id = data.get("customer_id")
    if not customer_id:
        return JsonResponse({"error": "customer_id required"}, status=400)

    # In a real view: Customer.objects.get(pk=customer_id), SaaSOrder.objects.create(…)
    # Illustrated here without DB:
    order_id = 42  # placeholder
    return JsonResponse(
        {
            "id": order_id,
            "customer_id": customer_id,
            "status": SaaSOrder.Status.PENDING,
        },
        status=201,
    )


# ==========================================================================
# SECTION 16 — Common Pitfalls Quick Reference
# ==========================================================================

PITFALLS = {
    "1_charfield_null": (
        "CharField with null=True creates two empty states (NULL + '').  "
        "Queries need Q(bio='') | Q(bio__isnull=True), uniqueness breaks.  "
        "Fix: blank=True only for string fields."
    ),
    "2_mutable_default": (
        "default=[] or default={} shares one object across all instances.  "
        "Fix: default=list or default=dict (callable, no parentheses)."
    ),
    "3_timezone_now_called": (
        "default=timezone.now() is evaluated at import time; all rows get "
        "the server start timestamp.  Fix: default=timezone.now (no parentheses)."
    ),
    "4_json_body_vs_post": (
        "JSON requests leave request.POST empty.  "
        "Fix: data = json.loads(request.body)."
    ),
    "5_cascade_on_financial_fk": (
        "on_delete=CASCADE on Invoice.customer deletes paid invoices when "
        "customer is removed.  Fix: PROTECT for financial / audit references."
    ),
    "6_json_list_without_safe_false": (
        "JsonResponse([…]) raises TypeError.  Fix: safe=False, or better: "
        "return JsonResponse({'results': […]}) — top-level dict always."
    ),
    "7_permanent_redirect_carelessly": (
        "301 is cached aggressively by browsers.  Wrong target deployed → "
        "users stuck even after fix deployed.  Fix: use 302 by default; "
        "only 301 when URL change is truly permanent."
    ),
    "8_installed_apps_forgotten": (
        "Models written, makemigrations says 'No changes detected'.  "
        "Fix: add app to INSTALLED_APPS."
    ),
    "9_template_namespace_skip": (
        "blog/templates/detail.html clashes with other apps.  "
        "Fix: always blog/templates/blog/detail.html (double dir)."
    ),
    "10_css_gone_on_debug_false": (
        "runserver stops serving static when DEBUG=False.  Expected behavior.  "
        "Fix: collectstatic + whitenoise/nginx/S3."
    ),
    "11_plain_m2m_too_late": (
        "Plain M2M → through= migration after data exists is painful.  "
        "Fix: use explicit through= from the start if relationship data is likely."
    ),
}


# ==========================================================================
# __main__ — demonstration (no DB required)
# ==========================================================================

if __name__ == "__main__":
    print("=" * 68)
    print("Django MVT, Fields & Relationships — Patterns Demonstration")
    print("=" * 68)

    # --- TextChoices usage ---
    print("\n[TextChoices]")
    print("Status choices:", Article.Status.choices)
    print("DRAFT value   :", Article.Status.DRAFT)          # 'draft'
    print("DRAFT label   :", Article.Status.DRAFT.label)    # 'Draft'
    print("Values list   :", Article.Status.values)

    # --- Priority IntegerChoices ---
    print("\n[IntegerChoices]")
    print("Priority HIGH:", Order.Status.PAID)
    print("SaaSOrder Status:", SaaSOrder.Status.choices)

    # --- Default pitfalls demonstration ---
    print("\n[default pitfalls]")
    demonstrate_default_pitfalls()

    # --- Pitfalls summary ---
    print("\n[Common Pitfalls]")
    for key, description in PITFALLS.items():
        print(f"  {key}: {description[:80]}…")

    # --- Settings examples printed (not executed) ---
    print("\n[Static/Media Settings Example]")
    print(STATIC_MEDIA_SETTINGS_EXAMPLE.strip()[:200], "…")

    print("\n[Prod Checklist]")
    print(PROD_STATIC_CHECKLIST)

    print("=" * 68)
    print("Module loaded successfully.  All patterns documented above.")
    print("=" * 68)
