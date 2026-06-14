"""
Django Internationalization (i18n) and Localization (l10n) — Production Patterns
==================================================================================

Covers the complete translation pipeline as used in a real multi-tenant travel
platform (Django 5.2, django-hosts subdomain routing):

  - Settings: USE_I18N, LANGUAGES, LOCALE_PATHS
  - LocaleMiddleware — exact position and why it matters
  - gettext vs gettext_lazy — the module-level freeze bug and how to avoid it
  - f-string trap with named %(x)s placeholders
  - Language detection order (URL prefix → cookie → Accept-Language → fallback)
  - i18n_patterns URL configuration for SEO-friendly multilingual URLs
  - Pluralization with ngettext / ngettext_lazy
  - format_lazy for combining lazy strings safely
  - l10n number/date formatting (USE_L10N removed in Django 5.x)
  - DB content translation: 5 strategies compared with production trade-offs
  - Celery background tasks: language context injection with translation.override()
  - Custom multi-tenant locale middleware
  - JavaScriptCatalog for frontend JS translation
  - .po / .mo file anatomy and the fuzzy-entry pitfall

All snippets are illustrative production-quality code.  External infrastructure
(databases, Celery broker) is not required at import time — this module is
designed to be read and studied, with a minimal __main__ demo that runs without
any Django server.

pip install django                      # Core framework
pip install django-modeltranslation     # Strategy 3a: column-based DB translation
pip install django-parler               # Strategy 3b: translation-table DB translation
pip install celery                      # Async task queue (Celery patterns section)
"""

# ==========================================================================
# 1. SETTINGS — i18n / l10n configuration
# ==========================================================================

# settings.py excerpt — annotated for study

SETTINGS_EXAMPLE = '''
# settings.py
from pathlib import Path
from django.utils.translation import gettext_lazy as _   # lazy for module-level calls

BASE_DIR = Path(__file__).resolve().parent.parent

# ── i18n ──────────────────────────────────────────────────────────────────
USE_I18N = True          # Translation machinery on (True by default)
USE_TZ = True            # Always store datetimes in UTC

LANGUAGE_CODE = 'en'     # Ultimate fallback language

# Restrict to the languages your translators actually support.
# Without this, Django tries ~100 built-in languages for every request.
LANGUAGES = [
    ('en', _('English')),
    ('hi', _('Hindi')),
    ('mr', _('Marathi')),
]

# Project-level .po / .mo files live here.
# Django also checks each INSTALLED_APP\'s locale/ directory (reverse app order).
LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# ── l10n ──────────────────────────────────────────────────────────────────
# Django 5.x NOTE: USE_L10N setting was DEPRECATED in 4.0 and REMOVED in 5.0.
# Localized formatting (numbers, dates) is ALWAYS on in Django 5.x.
# If you are on an older codebase and see USE_L10N = True, that is fine but
# the setting is ignored from Django 5.0 onward.

USE_THOUSAND_SEPARATOR = True   # 1234.56 → "1,234.56" in en; default is False

# Point Django at custom per-locale format files when you need to override
# built-in formats (e.g., custom DATE_FORMAT for Hindi locale).
FORMAT_MODULE_PATH = 'myproject.formats'
# Then create:  myproject/formats/hi/formats.py
#   DATE_FORMAT = 'j F Y'
#   DATETIME_FORMAT = 'j F Y, P'

# Cookie name written by set_language view (and read by LocaleMiddleware)
LANGUAGE_COOKIE_NAME = 'django_language'   # default — shown explicitly for clarity
'''

print(SETTINGS_EXAMPLE)

# ==========================================================================
# 2. MIDDLEWARE — LocaleMiddleware position (classic interview trap)
# ==========================================================================

MIDDLEWARE_EXAMPLE = '''
# settings.py — MIDDLEWARE list (order is load-bearing)

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',   # ① MUST come before Locale
    'django.middleware.locale.LocaleMiddleware',              # ② HERE — after Session
    'django.middleware.common.CommonMiddleware',              # ③ AFTER Locale
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# WHY this exact order?
# ① SessionMiddleware BEFORE LocaleMiddleware: documented convention (even though
#   Django 3.0+ stores language in a cookie, not the session, the ordering is
#   still required per Django docs to avoid subtle ordering bugs).
# ② CommonMiddleware AFTER LocaleMiddleware: CommonMiddleware handles APPEND_SLASH
#   redirects.  If language has not been resolved yet, the redirect URL could lose
#   its language prefix (/hi/about → /about/).
# ③ Cache middleware trap: if you use UpdateCacheMiddleware / FetchFromCacheMiddleware,
#   LocaleMiddleware must sit BETWEEN them so cached responses vary per language.
#   Correct order: UpdateCacheMiddleware → LocaleMiddleware → FetchFromCacheMiddleware.

# What LocaleMiddleware does on EVERY request:
#   1. Detects language (see Section 5 for full detection order).
#   2. Calls translation.activate(lang).
#   3. Sets request.LANGUAGE_CODE.
#   4. Adds Content-Language response header.
#   5. Adds Vary: Accept-Language response header (prevents CDN serving wrong language).
'''

print(MIDDLEWARE_EXAMPLE)

# ==========================================================================
# 3. TRANSLATION MARKING — gettext vs gettext_lazy
# ==========================================================================

# ── 3a. The module-level freeze bug ───────────────────────────────────────

# Imagine the following in models.py (runs at SERVER START, once, before any request):

# WRONG — gettext evaluates immediately at import time
# from django.utils.translation import gettext as _
#
# class TravelPackage(models.Model):
#     name = models.CharField(
#         max_length=200,
#         verbose_name=_("Package Name"),   # ← evaluated when Python imports this file
#     )                                      #   active language at import = LANGUAGE_CODE ('en')
#                                            #   string is FROZEN as "Package Name" forever

# CORRECT — lazy proxy evaluated at render time (per-request language in effect)
# from django.utils.translation import gettext_lazy as _
#
# class TravelPackage(models.Model):
#     name = models.CharField(max_length=200, verbose_name=_("Package Name"))
#     #  _("Package Name") returns a LazyObject.  When Django admin renders the page
#     #  and calls str() on it, the CURRENT request language is used → correct translation.

# ── 3b. Rule of thumb ─────────────────────────────────────────────────────

GETTEXT_RULE = '''
Use gettext_lazy (_) at:
  - Model verbose_name, help_text, choices
  - Form / serializer field labels, error messages
  - Module-level constants and class attributes
  - settings.py LANGUAGES list

Use gettext (plain) inside:
  - View function bodies (run per-request, language is already active)
  - Management command handle() bodies
  - Celery task bodies (after translation.override() is entered — Section 7)
'''

print(GETTEXT_RULE)


def view_body_example(request):
    """Plain gettext is fine inside view bodies — they execute per-request."""
    # pip install django
    from django.http import JsonResponse
    from django.utils.translation import gettext

    msg = gettext("Booking confirmed")       # ✓ request-time execution
    return JsonResponse({"message": msg})


# ── 3c. f-string trap ─────────────────────────────────────────────────────

F_STRING_TRAP = '''
# ❌ NEVER use f-strings inside _()
name = "Ashish"
count = 3

# Problem 1: f-string resolves BEFORE gettext sees the string.
#   msgid at runtime = "Welcome Ashish" — makemessages never extracts this,
#   so .po file will never have a matching msgid.
# Problem 2: each user produces a different msgid — untranslatable.
msg = _(f"Welcome {name}")                           # ❌ WRONG

# ❌ Positional placeholders prevent translators from reordering words.
#   German/Hindi often need a different word order.
msg = _("Today is %s %s") % (month, day)             # ❌ BAD

# ✓ Named placeholders — translator can reorder freely; msgfmt validates them.
msg = _("Welcome %(name)s, you have %(count)d bookings") % {
    "name": name,
    "count": count,
}
# Hindi translator can write: "%(name)s जी, आपकी %(count)d बुकिंग हैं"
# The makemessages flag #, python-format triggers msgfmt validation — a typo
# like %(nam)s causes a compile error, preventing a runtime KeyError in prod.
'''

print(F_STRING_TRAP)


# ── 3d. Demonstrable lazy string demo (no Django server needed) ────────────

class LazyStringDemo:
    """
    Illustrates that gettext_lazy returns a proxy, not an evaluated string.
    In a real Django app the active language is set per-request by LocaleMiddleware;
    here we manually activate a language to show the deferred evaluation.
    """

    @staticmethod
    def run():
        try:
            # pip install django
            import django
            from django.conf import settings as django_settings
            if not django_settings.configured:
                django_settings.configure(
                    USE_I18N=True,
                    LANGUAGE_CODE="en",
                    LANGUAGES=[("en", "English"), ("hi", "Hindi")],
                    INSTALLED_APPS=["django.contrib.contenttypes", "django.contrib.auth"],
                )
                django.setup()

            from django.utils.translation import gettext_lazy as lazy_gettext, activate

            # Lazy string created at "import time" (before any language activation)
            greeting = lazy_gettext("Welcome")
            print(f"Type of lazy string:  {type(greeting)}")

            activate("en")
            print(f"Language='en' → str(greeting) = '{str(greeting)}'")

            # NOTE: In a real app with .po files compiled, activating 'hi' would
            # return the Hindi translation.  Without .po files this falls back to
            # the msgid itself ("Welcome").
            activate("hi")
            print(f"Language='hi' → str(greeting) = '{str(greeting)}' (fallback: no .mo file)")

        except Exception as exc:
            print(f"[LazyStringDemo] Skipped — Django not fully configured: {exc}")


# ==========================================================================
# 4. PLURALIZATION — ngettext / ngettext_lazy
# ==========================================================================

def format_booking_count(count: int) -> str:
    """
    Correct pluralization using ngettext.

    Why not `if count == 1`?  Each language has its own plural rules:
      English:  1 form for singular, 1 for plural  (2 forms total)
      Russian:  3 plural forms
      Arabic:   6 plural forms
    The .po file header contains a Plural-Forms expression; gettext picks the
    correct form automatically based on that expression.
    """
    try:
        from django.utils.translation import ngettext
        msg = ngettext(
            "You have %(count)d booking",     # singular form
            "You have %(count)d bookings",    # plural form
            count,                            # determines which form to use
        ) % {"count": count}
        return msg
    except Exception:
        # Fallback for environments without Django configured
        word = "booking" if count == 1 else "bookings"
        return f"You have {count} {word}"


# Lazy variant for class/module level (e.g., form help_text)
# from django.utils.translation import ngettext_lazy
# SEAT_LABEL = ngettext_lazy("%(count)d seat", "%(count)d seats", "count")


# ==========================================================================
# 5. format_lazy — combining lazy strings without breaking laziness
# ==========================================================================

FORMAT_LAZY_EXAMPLE = '''
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

# ❌ f-string forces immediate evaluation — lazy is lost (import-time bug)
# help_text = f"{_("Note")}: {_("Prices include GST")}"

# ✓ format_lazy — returns a lazy object; both parts evaluated at render time
help_text = format_lazy(
    "{prefix}: {detail}",
    prefix=_("Note"),
    detail=_("Prices include GST"),
)
# When the form is rendered at request time, both lazy strings are translated
# into the current request language before concatenation.
'''

print(FORMAT_LAZY_EXAMPLE)


# ==========================================================================
# 6. LANGUAGE DETECTION ORDER
# ==========================================================================

DETECTION_ORDER = '''
LocaleMiddleware resolves language in this EXACT order (stop at first match):

  1. URL prefix        /hi/packages/   — only if i18n_patterns is used in urls.py
  2. Cookie            LANGUAGE_COOKIE_NAME (default: "django_language")
  3. Accept-Language   browser header, honour q-values; match against LANGUAGES
  4. LANGUAGE_CODE     settings.py fallback (never fails)

Historical note (important for senior interviews):
  Django <3.0 checked the SESSION ("django_language" key) BEFORE the cookie.
  Django 3.0 removed session-based language storage entirely.
  The set_language view now writes to a cookie only.
  If someone says "language is stored in the session" — that is outdated.
'''

print(DETECTION_ORDER)


# ==========================================================================
# 7. URL CONFIGURATION — i18n_patterns for SEO-friendly multilingual URLs
# ==========================================================================

URLS_EXAMPLE = '''
# urls.py (root URLconf)
from django.conf.urls.i18n import i18n_patterns
from django.urls import path, include
from django.views.i18n import JavaScriptCatalog

urlpatterns = [
    # Built-in set_language view — handles the language-switcher POST form
    path("i18n/", include("django.conf.urls.i18n")),

    # API endpoints do NOT need language prefixes (they use Accept-Language header
    # or an explicit ?lang= param per API contract)
    path("api/", include("api.urls")),

    # JavaScript translation catalog — serve once, cache aggressively
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
]

# i18n_patterns adds a language-code prefix to every enclosed URL.
urlpatterns += i18n_patterns(
    path("", include("pages.urls")),
    path("packages/", include("packages.urls")),
    # prefix_default_language=False → default language served at /packages/
    # (no /en/ prefix), Hindi at /hi/packages/.
    # This is the most common SEO pattern for Indian platforms: English at root,
    # regional languages with prefix.
    prefix_default_language=False,
)
'''

print(URLS_EXAMPLE)

SEO_COMPARISON = '''
URL strategy comparison (SEO-critical for public-facing travel platforms):

  Strategy              Example                          SEO         Notes
  ─────────────────     ──────────────────────────────   ─────────   ──────────────────────────────────────────────────────────
  URL prefix (best)     niroskos.com/hi/goa-packages/    ✓ Ideal    Unique crawlable URL per language; single domain authority;
                                                                      hreflang easy; built-in via i18n_patterns
  Subdomain             hi.niroskos.com/goa-packages/    ⚠ OK       Crawlable but Google may treat subdomains as semi-separate
                                                                      sites → domain authority split
  Cookie / session      niroskos.com/goa-packages/       ✗ Bad      Googlebot ignores cookies; only default language indexed

SEO checklist:
  - <link rel="alternate" hreflang="hi" href="..."> for every language version
  - <link rel="alternate" hreflang="x-default" href="..."> pointing at default
  - Include all language URLs in sitemap.xml
  - LocaleMiddleware automatically adds Vary: Accept-Language (CDN must respect it)
'''

print(SEO_COMPARISON)


# ==========================================================================
# 8. LANGUAGE ACTIVATION — activate() vs override()
# ==========================================================================

def language_activation_demo():
    """
    Shows the difference between translate.activate() (manual, must deactivate)
    and translation.override() (context manager, auto-restores previous language).
    """
    try:
        from django.utils import translation
        from django.utils.translation import gettext

        # ── translate.activate — low-level, manual cleanup required ───────────
        translation.activate("hi")
        msg = gettext("Search")          # uses 'hi' (or fallback if no .mo)
        translation.deactivate()         # MUST call this; otherwise language leaks
                                         # into the next task on the same thread

        # ── translation.override — PREFERRED in production code ───────────────
        with translation.override("hi"):
            msg = gettext("Search")      # language is 'hi' inside the block
        # Previous language automatically restored on __exit__
        # Thread-safe: override stores state per-thread using a stack.

        print(f"Activation demo complete. Last translated string: '{msg}'")

    except Exception as exc:
        print(f"[language_activation_demo] Skipped: {exc}")


# ==========================================================================
# 9. CELERY TASKS — injecting language context
# ==========================================================================

CELERY_LANGUAGE_EXAMPLE = '''
# tasks.py
from celery import shared_task
from django.utils import translation
from django.utils.translation import gettext
from django.core.mail import send_mail
from django.template.loader import render_to_string

@shared_task
def send_booking_confirmation_email(user_id: int, booking_id: int) -> None:
    """
    Send a booking confirmation email in the user\'s preferred language.

    Problem: Celery workers have no HTTP request, so LocaleMiddleware never runs.
    The active language on the worker thread is LANGUAGE_CODE ("en").
    Without an explicit override, every user receives English emails regardless
    of their profile language setting.

    Fix: store the user\'s preferred language in the DB and activate it explicitly.
    """
    from myapp.models import User, Booking   # local import avoids circular refs

    user = User.objects.select_related("profile").get(pk=user_id)
    booking = Booking.objects.get(pk=booking_id)

    # user.profile.language is a CharField storing e.g. "hi" or "en"
    user_language = getattr(user.profile, "language", "en")

    with translation.override(user_language):
        # Everything inside this block uses user_language
        subject = gettext("Your booking is confirmed")
        body = render_to_string(
            "emails/booking_confirmation.html",
            {"user": user, "booking": booking},
            # NOTE: render_to_string respects the currently active language
        )

    send_mail(subject, body, "noreply@niroskos.com", [user.email])


# WHY use override() rather than activate()?
# Celery reuses worker threads.  activate() without deactivate() leaks the
# language into the next task that runs on the same thread.  The context manager
# guarantees cleanup even if an exception is raised inside the block.
'''

print(CELERY_LANGUAGE_EXAMPLE)


# ==========================================================================
# 10. DB CONTENT TRANSLATION — 5 strategies
# ==========================================================================

# ── Strategy 1: Extra columns per language ─────────────────────────────────

STRATEGY_1_EXAMPLE = '''
# models.py — Strategy 1: Extra columns (best for 2–3 fixed languages)

from django.db import models
from django.utils import translation


class TravelPackage(models.Model):
    """
    Language-specific content stored as separate columns.
    Simple, no extra JOINs, normal B-tree indexes work for filter/order.
    Adding a new language = one migration + touching every form/serializer.
    """
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    # Translatable fields — one column set per supported language
    name_en = models.CharField(max_length=200)
    name_hi = models.CharField(max_length=200, blank=True)

    description_en = models.TextField()
    description_hi = models.TextField(blank=True)

    @property
    def name(self) -> str:
        """Return the name in the currently active language, falling back to English."""
        lang = translation.get_language() or "en"
        # translation.get_language() returns e.g. "hi-in" — take the base tag
        lang_base = lang.split("-")[0]
        value = getattr(self, f"name_{lang_base}", None)
        return value if value else self.name_en

    @property
    def description(self) -> str:
        lang = translation.get_language() or "en"
        lang_base = lang.split("-")[0]
        value = getattr(self, f"description_{lang_base}", None)
        return value if value else self.description_en

    class Meta:
        # Direct index on translated column — fast ORDER BY / filter
        indexes = [
            models.Index(fields=["name_en"], name="pkg_name_en_idx"),
            models.Index(fields=["name_hi"], name="pkg_name_hi_idx"),
        ]
'''

print(STRATEGY_1_EXAMPLE)

# ── Strategy 2: Separate translation table ─────────────────────────────────

STRATEGY_2_EXAMPLE = '''
# models.py — Strategy 2: Translation table (scales to many languages)

from django.db import models


class TravelPackageBase(models.Model):
    """Language-agnostic data lives here."""
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    def get_translation(self, lang: str):
        """Retrieve the translation row for the given language code."""
        return self.translations.filter(language=lang).first()


class PackageTranslation(models.Model):
    """One row per (package, language) pair."""
    package = models.ForeignKey(
        TravelPackageBase,
        on_delete=models.CASCADE,
        related_name="translations",
    )
    language = models.CharField(max_length=10)     # "hi", "en", "mr" …
    name = models.CharField(max_length=200)
    description = models.TextField()

    class Meta:
        unique_together = [("package", "language")]
        indexes = [
            models.Index(fields=["package", "language"], name="pkg_trans_pkg_lang_idx"),
        ]

# Querying with prefetch to avoid N+1:
# packages = TravelPackageBase.objects.filter(is_active=True)
#     .prefetch_related(
#         Prefetch(
#             "translations",
#             queryset=PackageTranslation.objects.filter(language=get_language()),
#             to_attr="current_translations",
#         )
#     )
# for pkg in packages:
#     trans = pkg.current_translations[0] if pkg.current_translations else None
#     name = trans.name if trans else ""
'''

print(STRATEGY_2_EXAMPLE)

# ── Strategy 4: JSONField per locale (PostgreSQL-centric) ──────────────────

STRATEGY_4_EXAMPLE = '''
# models.py — Strategy 4: JSONField (schema-free, PostgreSQL GIN index)

from django.db import models
from django.contrib.postgres.indexes import GinIndex
from django.utils import translation


class TravelPackageJSON(models.Model):
    """
    Translations stored as a JSON object keyed by language code.
    Zero schema change when adding a new language — just insert a new key.
    Querying on translated fields requires a GIN index for performance.
    """
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    name = models.JSONField(default=dict)        # {"en": "Goa Trip", "hi": "गोवा यात्रा"}
    description = models.JSONField(default=dict) # {"en": "...", "hi": "..."}

    @property
    def current_name(self) -> str:
        lang = (translation.get_language() or "en").split("-")[0]
        return self.name.get(lang) or self.name.get("en", "")

    class Meta:
        indexes = [
            # PostgreSQL GIN index required for jsonb_path_ops lookups
            GinIndex(fields=["name"], name="pkg_name_gin"),
        ]

# Filter example (PostgreSQL only):
# TravelPackageJSON.objects.filter(name__hi__icontains="गोवा")
# Without GIN index this is a full-table scan — add it before production traffic.
'''

print(STRATEGY_4_EXAMPLE)

DB_STRATEGY_COMPARISON = '''
DB content translation strategy comparison:

  Strategy                 New language cost      Query / filter         JOIN?   Best for
  ──────────────────────   ────────────────────   ─────────────────────  ──────  ─────────────────────────────────────
  Extra columns            Migration + code       Direct, B-tree index   No      2–3 fixed languages (most Indian platforms)
  Translation table        Insert rows only       JOIN / prefetch, N+1   Yes     5+ languages or dynamic language list
  django-modeltranslation  Migration (auto cols)  Transparent (obj.name) No      Strategy 1 with less boilerplate
  django-parler            Insert rows only       Manager handles, JOIN  Yes     Strategy 2 + polished admin UI (language tabs)
  JSONField                No schema change       name__hi lookups       No      Sparse/flexible, PostgreSQL + GIN index

Interview answer: "For Niroskos we chose extra columns (name_en / name_hi) because
our language list was fixed (en + hi) and we needed simple ORDER BY / filter queries
without joins.  Had we needed 10+ languages or a dynamic list we would have used
django-parler (translation table with polished admin support)."
'''

print(DB_STRATEGY_COMPARISON)


# ==========================================================================
# 11. TEMPLATE SNIPPETS — trans / blocktrans
# ==========================================================================

TEMPLATE_EXAMPLE = '''
{# templates/packages/list.html #}
{% load i18n %}

{# Simple literal string — Django 3.1+ also accepts {% translate %} as alias #}
<h1>{% trans "Popular Packages" %}</h1>

{# Store translated string in a variable for reuse #}
{% trans "Search" as search_label %}
<input type="text" placeholder="{{ search_label }}" aria-label="{{ search_label }}">

{# With variables — {% trans %} cannot interpolate variables; use blocktrans #}
{% blocktrans with name=user.first_name count=booking_count %}
    Welcome back, {{ name }}!  You have {{ count }} booking.
{% plural %}
    Welcome back, {{ name }}!  You have {{ count }} bookings.
{% endblocktrans %}

{# Template filters CANNOT go inside blocktrans — pre-compute with `with` #}
{% blocktrans with total=price|floatformat:2 currency=currency_code %}
    Total: {{ currency }}{{ total }}
{% endblocktrans %}

{# Get the current active language code for conditional logic #}
{% get_current_language as LANGUAGE_CODE %}
{% if LANGUAGE_CODE == "hi" %}
    <link rel="stylesheet" href="/static/fonts/devanagari.css">
{% endif %}

{# Language switcher form (POSTs to set_language built-in view) #}
<form action="{% url "set_language" %}" method="post">
    {% csrf_token %}
    <input name="next" type="hidden" value="{{ request.get_full_path }}">
    <select name="language" onchange="this.form.submit()">
        {% get_available_languages as LANGUAGES %}
        {% for code, name in LANGUAGES %}
            <option value="{{ code }}" {% if code == LANGUAGE_CODE %}selected{% endif %}>
                {{ name }}
            </option>
        {% endfor %}
    </select>
</form>

{#
  TRAPS:
  - {% trans some_var %} — runtime lookup that makemessages cannot extract.
    Use literal strings only: {% trans "Literal string" %}
  - f-string equivalent in templates: {% trans "Hello " %}{{ name }}
    is NOT the same as {% blocktrans %}Hello {{ name }}{% endblocktrans %}
    (the former produces two separate strings, only the first is translatable)
#}
'''

print(TEMPLATE_EXAMPLE)


# ==========================================================================
# 12. WORKFLOW — makemessages / compilemessages CLI
# ==========================================================================

WORKFLOW_COMMANDS = '''
# ── Extract strings from Python + HTML templates ──────────────────────────
python manage.py makemessages -l hi           # Hindi only
python manage.py makemessages -l mr           # Marathi only
python manage.py makemessages --all           # all languages in LANGUAGES

# ── JavaScript strings (separate domain!) ─────────────────────────────────
python manage.py makemessages -d djangojs -l hi
# Writes to locale/hi/LC_MESSAGES/djangojs.po
# Common mistake: translate Python strings, forget JS → frontend stays English.

# ── Compile .po → .mo (binary runtime file) ───────────────────────────────
python manage.py compilemessages
# OR compile a single language:
python manage.py compilemessages -l hi

# ── CI/CD recommendation ──────────────────────────────────────────────────
# Add compilemessages to your deployment step / Dockerfile build.
# .mo files are generated artifacts — some teams git-ignore them and compile
# on deploy; others commit them so production needs no build step.

# CRITICAL pitfall: translated .po file but forgot compilemessages
# → site still shows old/missing translations because Django reads .mo ONLY.
'''

print(WORKFLOW_COMMANDS)

PO_FILE_ANATOMY = '''
# locale/hi/LC_MESSAGES/django.po — annotated excerpt

# Translator comment set in Python source:
#   # Translators: Appears on the payment CTA button — means "reserve", not the noun "book"
#   label = _("Book")
#. Translators: Appears on the payment CTA button — means "reserve", not the noun "book"
#: packages/templates/packages/detail.html:42 packages/views.py:18
#, python-format
msgid "Your %(destination)s trip is confirmed"
msgstr "आपकी %(destination)s यात्रा confirm हो गई है"

# Fuzzy entry — makemessages found a close (but not exact) match to an old msgid.
# The #, fuzzy flag means msgfmt SKIPS this entry by default.
# Classic bug: "translation is in .po but not showing on the site" → fuzzy!
# Fix: translator reviews, updates msgstr if needed, removes the fuzzy flag.
#, fuzzy
msgid "Cancel booking"
msgstr "बुकिंग रद्द करें"

# Plural form example
#, python-format
msgid "You have %(count)d booking"
msgid_plural "You have %(count)d bookings"
msgstr[0] "आपकी %(count)d बुकिंग है"
msgstr[1] "आपकी %(count)d बुकिंगें हैं"
'''

print(PO_FILE_ANATOMY)


# ==========================================================================
# 13. JAVASCRIPT CATALOG — frontend translation
# ==========================================================================

JS_CATALOG_EXAMPLE = '''
# urls.py
from django.views.i18n import JavaScriptCatalog
urlpatterns += [
    # Cache this view aggressively — it only changes when .mo files change.
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
]

# In your base template:
# <script src="{% url "javascript-catalog" %}"></script>

# In your JavaScript (after the catalog script is loaded):
# const msg = gettext("Booking failed");           // mirrors Django\'s gettext
# const seats = ngettext("%s seat left", "%s seats left", count);
# alert(interpolate(seats, [count]));              // interpolate = sprintf-style
# const named = interpolate(
#     gettext("Welcome %(name)s"),
#     { name: "Ashish" },
#     true,                                        // true → named interpolation
# );

# Workflow for JS strings (commonly forgotten):
# 1. Mark JS strings with gettext() calls inside your .js files
# 2. python manage.py makemessages -d djangojs -l hi   ← -d djangojs is critical
# 3. Fill in locale/hi/LC_MESSAGES/djangojs.po
# 4. python manage.py compilemessages
# 5. The JavaScriptCatalog view serves the compiled translations as a JS file
'''

print(JS_CATALOG_EXAMPLE)


# ==========================================================================
# 14. CUSTOM TENANT LOCALE MIDDLEWARE (multi-tenant pattern)
# ==========================================================================

# Full middleware class — illustrative; requires django-hosts in real usage.

class TenantLocaleMiddleware:
    """
    Custom LocaleMiddleware for a multi-tenant platform using django-hosts.

    Language priority (highest to lowest):
      1. Explicit user choice stored in the language cookie
      2. Tenant (brand/agency) default language
      3. Site-wide LANGUAGE_CODE fallback

    Middleware order in settings.MIDDLEWARE:
      HostsRequestMiddleware      — resolves subdomain → sets request.tenant
      SessionMiddleware
      TenantLocaleMiddleware      ← this class (replaces standard LocaleMiddleware)
      CommonMiddleware
      ...
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = self._resolve_language(request)
        self._activate(request, lang)
        response = self.get_response(request)
        self._finalize(response)
        return response

    def _resolve_language(self, request) -> str:
        try:
            from django.conf import settings as django_settings
            cookie_name = getattr(django_settings, "LANGUAGE_COOKIE_NAME", "django_language")
            fallback = getattr(django_settings, "LANGUAGE_CODE", "en")
        except Exception:
            cookie_name, fallback = "django_language", "en"

        # ① Explicit user choice from language-switcher form
        cookie_lang = request.COOKIES.get(cookie_name)
        if cookie_lang:
            return cookie_lang

        # ② Tenant default (set by an upstream TenantMiddleware via django-hosts)
        tenant = getattr(request, "tenant", None)
        if tenant and hasattr(tenant, "default_language") and tenant.default_language:
            return tenant.default_language

        # ③ Accept-Language header matching against LANGUAGES
        try:
            from django.utils.translation import get_language_from_request
            accepted = get_language_from_request(request, check_path=False)
            if accepted:
                return accepted
        except Exception:
            pass

        # ④ Hard fallback
        return fallback

    def _activate(self, request, lang: str) -> None:
        try:
            from django.utils import translation
            translation.activate(lang)
            request.LANGUAGE_CODE = lang
        except Exception:
            request.LANGUAGE_CODE = lang

    def _finalize(self, response) -> None:
        try:
            from django.utils import translation
            active = translation.get_language() or "en"
            response.headers.setdefault("Content-Language", active)
            # Vary header is critical for CDN correctness — a CDN must not serve
            # a cached French page to a German speaker.
            response.setdefault("Vary", "Accept-Language")
            translation.deactivate()
        except Exception:
            pass


# ==========================================================================
# 15. l10n FORMATTING — numbers, dates, forms (Django 5.x)
# ==========================================================================

L10N_EXAMPLES = '''
# ── In templates (automatic once language is active) ──────────────────────
# {{ price }}       → en: 1,234.56  |  de: 1.234,56  |  hi: 1,234.56
# {{ trip_date }}   → locale-specific date representation

# ── Disable localization for a single value (e.g., a numeric ID) ──────────
# {% load l10n %}
# {{ product_id|unlocalize }}    → always "1234", never "1,234"

# ── Form fields with localized parsing ────────────────────────────────────
# class BookingForm(forms.Form):
#     price = forms.DecimalField(localize=True)
#     # German user types "1.234,56" → correctly parsed as Decimal("1234.56")
#     # Without localize=True the default validator rejects the comma separator.

# ── Custom locale format file ─────────────────────────────────────────────
# myproject/formats/hi/formats.py
# DATE_FORMAT = "j F Y"               # "12 जून 2026"
# DATETIME_FORMAT = "j F Y, P"
# DATE_INPUT_FORMATS = ["%d/%m/%Y"]   # Indian convention for form inputs
# NUMBER_GROUPING = 3
# THOUSAND_SEPARATOR = ","
# DECIMAL_SEPARATOR = "."

# Then in settings.py:
# FORMAT_MODULE_PATH = "myproject.formats"
'''

print(L10N_EXAMPLES)


# ==========================================================================
# 16. COMMON PITFALLS — quick reference card
# ==========================================================================

PITFALL_CARD = """
Common i18n / l10n pitfalls (memorize for interviews):

  #  Pitfall                               Root cause / fix
  ─  ────────────────────────────────────  ──────────────────────────────────────────────────────────
  1  gettext at module level               Import-time freeze → use gettext_lazy
  2  _( f"Hello {name}" )                 makemessages cannot extract; f-string resolves before gettext
                                           → use _("Hello %(name)s") % {"name": name}
  3  compilemessages not run after .po     Django reads .mo only; stale .mo = missing/old translations
  4  Fuzzy entries skipped                 #, fuzzy flag → msgfmt skips by default; translator must review
  5  LocaleMiddleware wrong position       Language not resolved → missing Content-Language/Vary headers
  6  Celery/cron with default language     No request context → use translation.override(user.language)
  7  {% trans some_variable %}             makemessages cannot extract runtime vars; use literal strings
  8  Forgot -d djangojs for JS strings    makemessages only extracts Python/HTML; JS needs separate domain
  9  DB content via gettext                makemessages cannot read the DB → use a DB translation strategy
 10  Cookie-only language on public pages  Googlebot ignores cookies → only default language indexed by SEO
"""

print(PITFALL_CARD)


# ==========================================================================
# __main__ demo — runs without a Django server or database
# ==========================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Django i18n / l10n — standalone demo")
    print("=" * 70)

    # ── Demo 1: lazy string evaluation ────────────────────────────────────
    print("\n[1] Lazy string evaluation demo:")
    LazyStringDemo.run()

    # ── Demo 2: pluralization (no .po files required — uses fallback) ─────
    print("\n[2] Pluralization demo (English fallback — no .po files required):")
    for n in (0, 1, 2, 10):
        print(f"    count={n:2d}  →  {format_booking_count(n)}")

    # ── Demo 3: TenantLocaleMiddleware (unit-level smoke test) ────────────
    print("\n[3] TenantLocaleMiddleware — mock request smoke test:")

    class MockRequest:
        COOKIES = {"django_language": "hi"}
        headers = {}
        META = {}
        tenant = None

    class MockResponse:
        headers = {}
        _store: dict = {}

        def setdefault(self, key, value):
            if key not in self._store:
                self._store[key] = value

    def mock_get_response(_req):
        return MockResponse()

    middleware = TenantLocaleMiddleware(mock_get_response)
    mock_req = MockRequest()
    resp = middleware(mock_req)
    print(f"    request.LANGUAGE_CODE set to: {getattr(mock_req, 'LANGUAGE_CODE', 'N/A')}")
    print(f"    Content-Language header:       {resp.headers.get('Content-Language', 'N/A')}")

    print("\n" + "=" * 70)
    print("All demos complete.")
    print("For full translation workflow, run inside a Django project:")
    print("  python manage.py makemessages -l hi")
    print("  # fill in locale/hi/LC_MESSAGES/django.po")
    print("  python manage.py compilemessages")
    print("=" * 70)
