# Django i18n & l10n Deep — Translation, Locale, Multi-Language Architecture
## Django/DRF — Interview Prep (Hinglish Style)

## Why It Matters

Resume pe "multi-language i18n" likha hai (Niroskos — multi-tenant travel platform, Django 5.2, django-hosts subdomain routing) → interviewer yahan **zaroor** drill karega. Yeh topic do levels pe poocha jata hai:

1. **Junior level:** `gettext` vs `gettext_lazy`, `makemessages` workflow, middleware position
2. **Senior level:** "User-generated content (hotel names, package descriptions) ka translation kaise kiya? DB strategy kya thi? SEO ke liye URL structure kya rakha?" — yeh REAL question hai kyunki static UI strings translate karna easy hai, **DB content translate karna architecture decision hai**.

---

## SECTION A — i18n vs l10n vs Timezone: Definitions

Pehle terminology clear karo — interviewer often opening question yahi puchta hai.

| Term | Full Form | Matlab | Django Setting | Example |
|---|---|---|---|---|
| **i18n** | Internationalization (i + 18 letters + n) | App ko translation-READY banana — strings mark karna, hardcoding hatana | `USE_I18N = True` | `_("Welcome")` likhna instead of `"Welcome"` |
| **l10n** | Localization (l + 10 letters + n) | Specific locale ke FORMAT apply karna — dates, numbers, currency | (Django 5.x me always on) | `1,234.56` (en) vs `1.234,56` (de) vs `1,234.56` (hi) |
| **tz** | Timezone handling | UTC me store, user ke timezone me display | `USE_TZ = True` | DB me UTC, user ko IST dikhana |

**One-liner yaad rakho:** i18n = "translate karne ki capability" (developer ka kaam), l10n = "ek locale ke liye actual adaptation" (translator + formats ka kaam). Teeno independent hain — i18n off karke bhi tz on rakh sakte ho.

---

## SECTION B — Setup: Settings + Middleware

```python
# settings.py
from django.utils.translation import gettext_lazy as _

USE_I18N = True                  # Translation machinery on (default True)
USE_TZ = True                    # Timezone-aware datetimes

LANGUAGE_CODE = 'en'             # Fallback/default language

# Sirf yeh languages serve karni hain (warna Django ~100 languages try karega)
LANGUAGES = [
    ('en', _('English')),
    ('hi', _('Hindi')),
    ('mr', _('Marathi')),
]

# .po files yahan dhoondhega (project-level translations)
LOCALE_PATHS = [
    BASE_DIR / 'locale',
]
# Note: har app ke andar bhi `locale/` folder ho sakta hai — Django dono check karta hai.
# Resolution order: LOCALE_PATHS pehle, phir INSTALLED_APPS ke locale dirs (reverse order).
```

### LocaleMiddleware — Position MATTERS (classic trap)

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',   # 1. PEHLE yeh
    'django.middleware.locale.LocaleMiddleware',              # 2. PHIR yeh
    'django.middleware.common.CommonMiddleware',              # 3. USKE BAAD yeh
    # ... baaki
]
```

**Kyun yeh exact position?**
- **SessionMiddleware ke BAAD** — kyunki language detection ko session data accessible hona chahiye (legacy reason; modern Django cookie use karta hai, but session middleware ke baad rakhna documented convention hai).
- **CommonMiddleware se PEHLE** — kyunki CommonMiddleware `APPEND_SLASH` redirects karta hai aur usse pehle language resolve honi chahiye, warna `/hi/about` → redirect me language prefix kho sakta hai.
- **Bonus trap:** agar `UpdateCacheMiddleware` use kar rahe ho to LocaleMiddleware uske BAAD aana chahiye (cache middleware sabse upar hota hai), kyunki cached responses language ke hisaab se vary hone chahiye.

LocaleMiddleware kya karta hai: har request pe language detect karta hai → `translation.activate(lang)` → `request.LANGUAGE_CODE` set karta hai → response me `Content-Language` header + `Vary: Accept-Language` add karta hai (taaki CDN/proxy galat language cache na kare).

---

## SECTION C — Translation Marking: gettext vs gettext_lazy

### The Core Difference — Evaluation Timing

```python
from django.utils.translation import gettext, gettext_lazy

gettext("Welcome")        # ABHI translate karo — current active language me string return
gettext_lazy("Welcome")   # ABHI mat karo — lazy proxy object return, jab string ki tarah
                          # USE hoga (str() / render) TAB translate hoga
```

### The Bug Demo — module level pe gettext KYUN nahi

```python
# models.py — yeh module IMPORT time pe execute hota hai (server start pe, EK BAAR)

from django.utils.translation import gettext as _          # ❌ WRONG yahan

class TravelPackage(models.Model):
    name = models.CharField(
        max_length=200,
        verbose_name=_("Package Name"),    # ❌ BUG!
    )
```

**Yeh trap isliye hota hai kyunki:** `models.py` server startup pe import hota hai — us waqt koi request nahi hai, active language = `LANGUAGE_CODE` (maan lo `'en'`). To `_("Package Name")` turant evaluate hoke `"Package Name"` (English) ban jata hai aur **hamesha ke liye freeze**. Ab Hindi user aaye to bhi admin/forms me English hi dikhega — kyunki translation import time pe ho chuki, request time pe nahi.

```python
from django.utils.translation import gettext_lazy as _     # ✅ CORRECT

class TravelPackage(models.Model):
    name = models.CharField(max_length=200, verbose_name=_("Package Name"))
    # Lazy proxy store hota hai. Jab admin page render hoga (request time),
    # TAB str() call hoga aur us request ki active language me translate hoga.
```

**Rule of thumb:**
- **Module/class level** (models `verbose_name`, `help_text`, `choices`, form labels, settings) → `gettext_lazy`
- **Function/view body ke andar** (request ke time execute hota hai) → `gettext` theek hai

```python
def my_view(request):
    msg = gettext("Booking confirmed")   # ✅ OK — request time pe run hota hai
    return JsonResponse({'message': msg})
```

### Lazy ka ek aur trap — string operations

```python
title = gettext_lazy("Packages")
full = "All " + title          # ❌ TypeError ya premature evaluation issues
full = f"All {title}"          # ❌ f-string lazy ko ABHI str() kar dega — laziness toot gayi
```

Lazy strings combine karne ke liye → `format_lazy` (Section H me).

### ugettext history (one-liner for interview)

`ugettext`/`ugettext_lazy` Python 2 era ke "unicode" variants the — Python 3 me sab strings unicode hain to redundant ho gaye; **Django 3.0 me deprecated, 4.0 me removed**. Purane codebase me dikhe to seedha `gettext` se replace karo.

### The f-string Trap — gettext me % named placeholders KYUN

```python
# ❌ NEVER — f-string gettext se PEHLE evaluate hota hai
name = "Ashish"
msg = _(f"Welcome {name}")
# Problem 1: makemessages ko literal string chahiye — yeh extract hi nahi hogi
#            (msgid runtime pe "Welcome Ashish" banega — .po me kabhi match nahi karega)
# Problem 2: har user ke liye alag msgid — translation impossible

# ❌ BAD — positional, translator reorder nahi kar sakta
msg = _("Today is %s %s") % (month, day)
# German me order ulta chahiye ho sakta hai — positional me translator phas jayega

# ✅ CORRECT — named placeholders, translation ke BAAD interpolation
msg = _("Welcome %(name)s, you have %(count)d bookings") % {
    'name': name, 'count': count,
}
# Translator .po me likh sakta hai: "%(name)s जी, आपकी %(count)d bookings हैं"
# — placeholders ko REORDER kar sakta hai, yeh named ka pura point hai.
```

`makemessages` named placeholders dekh ke `.po` me `#, python-format` flag lagata hai — `msgfmt` phir validate karta hai ki translator ne placeholders galat to nahi kiye (typo `%(nam)s` → compile error, runtime crash se bachaya).

---

## SECTION D — Templates: trans / blocktrans

```django
{% load i18n %}   {# Har template me jahan translation chahiye #}

{# Simple string — Django 3.1+ me {% translate %} alias bhi hai #}
<h1>{% trans "Popular Packages" %}</h1>

{# Variable me store karna #}
{% trans "Search" as search_label %}
<button title="{{ search_label }}">{{ search_label }}</button>

{# Variables ke saath — {% trans %} me variable NAHI ja sakta, blocktrans chahiye #}
{% blocktrans with name=user.first_name %}
    Welcome back, {{ name }}!
{% endblocktrans %}

{# Pluralization — count keyword #}
{% blocktrans count counter=bookings|length %}
    You have {{ counter }} booking.
{% plural %}
    You have {{ counter }} bookings.
{% endblocktrans %}
```

**Traps:**
- `{% trans "..." %}` me sirf **literal string** — `{% trans some_var %}` runtime lookup karta hai jo `makemessages` extract nahi kar sakta (translation missing milegi).
- `{% blocktrans %}` ke andar template tags/filters **nahi** chal sakte — pehle `with` se compute karo: `{% blocktrans with total=price|floatformat:2 %}`.
- Current language template me chahiye to: `{% get_current_language as LANGUAGE_CODE %}`.

---

## SECTION E — Workflow: makemessages → translate → compilemessages

```bash
# 1. Strings extract karo → locale/hi/LC_MESSAGES/django.po banega
python manage.py makemessages -l hi
python manage.py makemessages --all          # sab LANGUAGES ke liye
python manage.py makemessages -d djangojs -l hi   # JS files ke liye (alag domain!)

# 2. Translator .po file me msgstr bharta hai

# 3. Compile karo → binary .mo file (yehi runtime pe use hoti hai)
python manage.py compilemessages
```

### .po file anatomy

```po
#. Translators: Yeh booking confirmation email ka subject hai
#: bookings/views.py:42
#, python-format
msgid "Your %(destination)s trip is confirmed"
msgstr "आपकी %(destination)s यात्रा confirm हो गई है"

#, fuzzy
msgid "Cancel booking"
msgstr "बुकिंग रद्द करें"
```

**Key cheezein:**
- **`.po` = source (human-readable), `.mo` = compiled binary** — Django runtime pe SIRF `.mo` padhta hai. Translation update kiya but `compilemessages` bhool gaye = purani translation dikhti rahegi (classic "translation kaam nahi kar raha" bug). `.mo` files git me commit karna ya deploy step me compile karna — team decision.
- **`fuzzy` entries:** jab source string thodi change hoti hai, `makemessages` purani translation ko guess-match karke `#, fuzzy` flag laga deta hai. **Fuzzy entries compile NAHI hoti by default** (msgfmt skip karta hai) — translator ko review karke fuzzy flag hatana padta hai. Trap: "translation .po me hai par site pe nahi aa rahi" → fuzzy check karo.
- **Translator comments:** code me `# Translators: ...` comment marked string ke theek upar likho — woh `.po` me `#.` ban ke pahunchta hai. Context dene ke liye critical: "Book" = kitaab ya reserve karna?

```python
# Translators: This appears on the payment button, means "reserve", not the noun
label = _("Book")
```

---

## SECTION F — Language Detection Order (DEEP — yeh ratta maaro)

`LocaleMiddleware` is exact order me language decide karta hai:

```
1. URL prefix          → /hi/packages/  (sirf agar i18n_patterns use kiya hai)
2. Cookie              → LANGUAGE_COOKIE_NAME (default: 'django_language')
3. Accept-Language     → browser header, q-values ke order me, LANGUAGES se match
4. LANGUAGE_CODE       → settings ka final fallback
```

**History trap (interviewer isse seniors ko pakadta hai):** purane Django (<3.0) me cookie se PEHLE **session** check hoti thi (`django_language` session key). Django 3.0 me session-based language storage **remove** ho gaya — ab `set_language` view cookie me hi store karta hai. Agar kisi ne bola "session me language store hoti hai" to woh outdated Django gyaan hai.

### i18n_patterns — URL prefix

```python
# urls.py (ROOT urlconf)
from django.conf.urls.i18n import i18n_patterns
from django.urls import path, include

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),   # set_language view yahan milta hai
    path('api/', include('api.urls')),                  # APIs ko prefix NAHI chahiye
]

urlpatterns += i18n_patterns(
    path('', include('pages.urls')),
    path('packages/', include('packages.urls')),
    prefix_default_language=False,   # /packages/ = English, /hi/packages/ = Hindi
)
```

`prefix_default_language=False` → default language bina prefix ke serve hoti hai. SEO ke liye yeh common pattern hai (English homepage `/` pe, Hindi `/hi/` pe).

### set_language — built-in language switcher

```django
<form action="{% url 'set_language' %}" method="post">
    {% csrf_token %}
    <input name="next" type="hidden" value="{{ request.get_full_path }}">
    <select name="language" onchange="this.form.submit()">
        {% get_available_languages as LANGUAGES %}
        {% for code, name in LANGUAGES %}
            <option value="{{ code }}">{{ name }}</option>
        {% endfor %}
    </select>
</form>
```

POST pe Django: cookie set karta hai + `next` URL pe redirect (i18n_patterns ho to URL me prefix bhi badal deta hai).

### Code me manually: activate() / override()

```python
from django.utils import translation

translation.activate('hi')        # Current thread ke liye language switch — WAPAS reset
                                  # karna tumhari zimmedari (ya deactivate())

with translation.override('hi'):  # ✅ Preferred — context manager, auto-restore
    subject = gettext("Booking Confirmed")
```

### Celery tasks me — THE classic production bug

```python
# Celery worker me koi request nahi, koi LocaleMiddleware nahi
# → active language = LANGUAGE_CODE (en). Hindi user ko English email chala jata hai!

@shared_task
def send_booking_email(user_id, booking_id):
    user = User.objects.get(pk=user_id)
    with translation.override(user.profile.language):   # ✅ User ki saved language activate
        subject = gettext("Your booking is confirmed")
        body = render_to_string('emails/booking.html', {...})
    send_mail(subject, body, ...)
```

**Lesson:** request ke bahar (Celery, management commands, cron) language context EXIST hi nahi karta — user ki preferred language DB me store karo (`profile.language`) aur explicitly `override()` karo.

---

## SECTION G — Model/DB Content Translation (THE REAL INTERVIEW QUESTION)

`gettext` sirf **static strings** ke liye hai jo code me likhi hain. Par travel platform me hotel names, package descriptions, city guides — yeh **DB me user/admin content** hai. `makemessages` DB nahi padh sakta. Yahan architecture decision aati hai:

### Strategy 1 — Extra fields per language (`name_en`, `name_hi`)

```python
class TravelPackage(models.Model):
    name_en = models.CharField(max_length=200)
    name_hi = models.CharField(max_length=200, blank=True)
    description_en = models.TextField()
    description_hi = models.TextField(blank=True)

    @property
    def name(self):
        lang = translation.get_language()                    # 'hi' ya 'en'
        return getattr(self, f'name_{lang}', '') or self.name_en   # fallback English
```

Simple, zero dependency, normal indexes/queries (`filter(name_hi__icontains=...)` seedha chalti hai). **2-3 languages tak best.** Naya language = migration + har query/form touch karna padta hai.

### Strategy 2 — Separate translation table

```python
class TravelPackage(models.Model):
    base_price = models.DecimalField(max_digits=10, decimal_places=2)

class PackageTranslation(models.Model):
    package = models.ForeignKey(TravelPackage, on_delete=models.CASCADE,
                                related_name='translations')
    language = models.CharField(max_length=10)
    name = models.CharField(max_length=200)
    description = models.TextField()

    class Meta:
        unique_together = [('package', 'language')]
```

Languages = rows, schema change nahi. Par har read pe JOIN/prefetch chahiye (`prefetch_related('translations')` warna N+1!), ordering-by-translated-field complex.

### Strategy 3 — Packages

- **django-modeltranslation:** registration-based — internally Strategy 1 jaisi columns (`name_en`, `name_hi`) ADD karta hai existing model me, admin integration free, `obj.name` automatically current language return karta hai. Migration-heavy par query-friendly.
- **django-parler:** Strategy 2 (translation table) ka polished version — `TranslatableModel` + `objects.translated('hi')` manager, admin tabs per language.

### Strategy 4 — JSONField per locale

```python
class TravelPackage(models.Model):
    name = models.JSONField(default=dict)    # {"en": "Goa Trip", "hi": "गोवा यात्रा"}

# Query (PostgreSQL):
TravelPackage.objects.filter(name__hi__icontains='गोवा')
# GIN index lagana padega for performance:
#   models.Index(fields=['name'], name='pkg_name_gin', opclasses=['jsonb_path_ops'])  — via GinIndex
```

### Comparison Table (interview me yeh bol do, senior lagoge)

| Strategy | New language cost | Query/Filter | Index | JOIN? | Best for |
|---|---|---|---|---|---|
| Extra fields (`name_hi`) | Migration + code touch | Direct, simple | Normal B-tree per column | No | 2–3 fixed languages (most Indian platforms) |
| Translation table | Sirf rows insert | JOIN/prefetch needed, N+1 risk | Composite (obj, lang) | Yes | 5+ languages, language list dynamic |
| django-modeltranslation | Migration (auto columns) | Transparent (`obj.name`) | Normal | No | Strategy 1 + kam boilerplate chahiye |
| django-parler | Rows only | Manager handles, still JOIN | Composite | Yes | Strategy 2 + admin UI chahiye |
| JSONField | Zero schema change | `name__hi` lookups, GIN needed | GIN (Postgres) | No | Flexible/sparse translations, NoSQL-ish comfort |

**Model answer line:** "Static UI strings ke liye gettext + .po workflow, DB content ke liye humne [extra-fields / modeltranslation] choose kiya kyunki languages fixed thi (en/hi) aur queries simple rehni thi — agar 10+ languages hoti to translation table / parler lete."

---

## SECTION H — Pluralization: ngettext + format_lazy

```python
from django.utils.translation import ngettext, ngettext_lazy

count = bookings.count()
msg = ngettext(
    "You have %(count)d booking",      # singular
    "You have %(count)d bookings",     # plural
    count,                              # is number pe decide hota hai
) % {'count': count}
```

**`if count == 1` manually KYUN nahi?** Kyunki har language ke plural rules alag hain — Russian me 3 plural forms hain, Arabic me 6! `.po` file ke header me `Plural-Forms:` expression hota hai, gettext usi se correct form pick karta hai. Tumhara English-centric `if` logic Russian me galat hoga.

### format_lazy — lazy strings combine karna

```python
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

# ❌ f-string / % lazy ko turant evaluate kar dega (import time pe — wahi bug)
# ✅ format_lazy = .format() ka lazy version
help_text = format_lazy(
    '{prefix}: {detail}',
    prefix=_('Note'),
    detail=_('Prices include GST'),
)
# Yeh khud bhi lazy hai — render time pe dono parts current language me aayenge
```

---

## SECTION I — l10n: Formats (Django 5.x)

**Trap question:** "USE_L10N kahan set karte ho?" → **Django 5.0 se yeh setting REMOVED hai** (4.0 me deprecated thi). Localized formatting ab hamesha ON hai. Tumhara platform Django 5.2 hai — yeh confidently bolo.

```python
# Locale ke hisaab se formatting — automatic in templates
{{ price }}        # en: 1,234.56  |  de: 1.234,56  |  hi: 1,234.56
{{ trip_date }}    # en: June 12, 2026  |  hi locale formats per LANG files

# Number formatting settings
USE_THOUSAND_SEPARATOR = True   # default False — explicitly on karna padta hai

# Per-value control in templates:
{% load l10n %}
{{ product_id|unlocalize }}     # ID me comma NAHI chahiye (1,234 nahi — 1234)

# Forms me localized input parsing:
class BookingForm(forms.Form):
    price = forms.DecimalField(localize=True)
    # German user "1.234,56" type karega → correctly Decimal('1234.56') parse hoga
    # localize=False (default) hota to ValidationError aata
```

Custom formats per locale: `FORMAT_MODULE_PATH = 'myproject.formats'` → `formats/hi/formats.py` me `DATE_FORMAT = 'j F Y'` etc. define karo.

---

## SECTION J — JavaScript Frontend: JavaScriptCatalog

Frontend JS me bhi strings hain (alerts, dynamic UI). Unke liye Django translation catalog as-JS serve karta hai:

```python
# urls.py
from django.views.i18n import JavaScriptCatalog

urlpatterns += [
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
]
```

```html
<script src="{% url 'javascript-catalog' %}"></script>
<script>
    const msg = gettext('Booking failed');           // JS me gettext() milta hai!
    const n = ngettext('%s seat left', '%s seats left', count);
    alert(interpolate(n, [count]));
</script>
```

Workflow: JS strings ke liye **alag domain** — `makemessages -d djangojs -l hi` → `djangojs.po`. Yeh bhoolna common hai: Python strings translate ho gayi, JS English me hi reh gaya.

---

## SECTION K — Multi-Tenant Angle (Niroskos pattern: django-hosts + per-tenant language)

Multi-tenant travel platform me har tenant (agency/brand) ki **apni default language** ho sakti hai. django-hosts subdomain routing ke saath tie karna:

```python
# Custom middleware — django-hosts ke HostsRequestMiddleware ke BAAD,
# aur LocaleMiddleware ki JAGAH ya uske custom variant ke roop me
class TenantLocaleMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # django-hosts ne subdomain resolve kar diya → tenant nikala
        tenant = getattr(request, 'tenant', None)   # TenantMiddleware ne set kiya

        # Priority: user ka explicit choice (cookie) > tenant default > site default
        lang = (
            request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
            or (tenant.default_language if tenant else None)
            or settings.LANGUAGE_CODE
        )
        translation.activate(lang)
        request.LANGUAGE_CODE = lang

    def process_response(self, request, response):
        response.headers.setdefault('Content-Language', translation.get_language())
        translation.deactivate()
        return response
```

**Key design point:** tenant resolution (subdomain) PEHLE honi chahiye, language activation BAAD me — to middleware order: `HostsRequestMiddleware` → `TenantMiddleware` → `TenantLocaleMiddleware`.

### URL Strategy Comparison — SEO ke liye CRITICAL (SEO-focused platform tha)

| Strategy | Example | SEO | Setup | Verdict |
|---|---|---|---|---|
| **URL prefix** | `niroskos.com/hi/goa-packages/` | ✅ Best — har language ka unique crawlable URL, `hreflang` easy, ek domain ki authority sab languages share karti hain | `i18n_patterns` built-in | **Default choice** |
| **Subdomain per lang** | `hi.niroskos.com/goa-packages/` | ⚠️ OK — crawlable, par Google subdomains ko semi-separate sites treat kar sakta hai → domain authority split | django-hosts se natural fit (tenant subdomains already hain) | Tab lo jab language = tenant-level separation chahiye |
| **Cookie/session only** | `niroskos.com/goa-packages/` (same URL, content badle) | ❌ WORST — Googlebot cookies nahi bhejta, default Accept-Language se sirf EK version index hoga; baaki languages SEO ke liye INVISIBLE | `set_language` only | Logged-in dashboards ke liye theek, public pages ke liye kabhi nahi |

**SEO checklist jo bolna chahiye:** har language version pe `<link rel="alternate" hreflang="hi" href="...">` tags + `x-default`, sitemap me sab language URLs, aur `Vary: Accept-Language` header (LocaleMiddleware free me deta hai).

---

## Common Pitfalls (Recap)

1. **`gettext` at module level** → import-time freeze, translation kabhi switch nahi hoti. `gettext_lazy` use karo.
2. **f-string inside `_()`** → makemessages extract nahi karega, msgid runtime pe banta hai. Named `%(x)s` placeholders.
3. **compilemessages bhool gaye** → `.po` updated, `.mo` purana, site pe purani/missing translation.
4. **Fuzzy entries** → .po me translation hai par compile nahi hui. Review karke fuzzy flag hatao.
5. **LocaleMiddleware galat position** → language detection broken ya cache poisoning.
6. **Celery/cron me language activate nahi ki** → sab background emails default language me.
7. **`{% trans variable %}`** → extract nahi hota, literal strings hi mark karo.
8. **JS strings ke liye `-d djangojs` bhool jana** → frontend half-translated.
9. **DB content ko gettext se translate karne ki koshish** → impossible; DB strategy chahiye (Section G).
10. **Cookie-only language switching on public SEO pages** → search engines ek hi language index karenge.

---

## Interview Q&A

**Q1:** i18n, l10n aur timezone support me difference?
**A:** i18n = app ko translatable banana (strings mark karna, `USE_I18N`); l10n = locale-specific formatting (dates/numbers — Django 5.x me always on, `USE_L10N` removed); tz = UTC storage + local display (`USE_TZ`). Teeno independent toggles/concerns hain.

**Q2:** `gettext` vs `gettext_lazy` — kab kya?
**A:** `gettext` immediately translate karta hai (current active language). `gettext_lazy` proxy return karta hai jo string-use ke waqt translate hota hai. Module/class level (models verbose_name, choices, form labels) pe lazy MANDATORY — kyunki woh code import time pe run hota hai jab request language pata hi nahi. View body me plain gettext theek hai.

**Q3:** LocaleMiddleware kahan rakhte ho aur kyun?
**A:** SessionMiddleware ke baad, CommonMiddleware se pehle. Cache middleware ho to uske baad. Yeh middleware language detect karke `translation.activate()` karta hai aur `Content-Language` + `Vary: Accept-Language` headers set karta hai.

**Q4:** Django language kaise decide karta hai? Exact order?
**A:** (1) URL prefix agar `i18n_patterns` use hua, (2) language cookie (`django_language`), (3) `Accept-Language` header q-values ke order me LANGUAGES se match, (4) `LANGUAGE_CODE` fallback. Bonus: Django 3.0 se pehle cookie se pehle session check hoti thi — ab removed.

**Q5:** `_(f"Hello {name}")` me kya problem hai?
**A:** Do problems: f-string gettext call se PEHLE evaluate hota hai to msgid runtime pe banta hai — `makemessages` extract nahi kar sakta aur `.po` me kabhi match nahi hoga. Fix: `_("Hello %(name)s") % {'name': name}` — named placeholders isliye taaki translator word order change kar sake (German/Hindi me order alag hota hai) aur `python-format` flag se msgfmt placeholder typos catch kare.

**Q6:** Celery task se user ko email bhejni hai uski language me — kaise?
**A:** Worker me request context nahi hota to active language = `LANGUAGE_CODE`. User ki preferred language DB me store karo (profile/model field), task me `with translation.override(user.profile.language):` ke andar subject/body render karo. Context manager use karna better hai kyunki worker thread reuse hota hai — `activate()` leak kar sakta hai next task me.

**Q7:** Static strings to gettext se ho gayi — DB content (package names, descriptions) kaise translate kiya?
**A:** 4 strategies: (1) extra columns `name_en`/`name_hi` — simple, direct queries/indexes, 2-3 languages best; (2) separate translation table — languages as rows, JOIN cost, scales; (3) packages — django-modeltranslation (column-based, transparent access) ya django-parler (table-based, admin tabs); (4) JSONField `{"en":..., "hi":...}` — schema-free, GIN index chahiye Postgres me. Choice languages ki count aur query patterns pe depend karti hai.

**Q8:** Pluralization manually `if count == 1` se kyun nahi?
**A:** Har language ke plural rules alag — Russian me 3 forms, Arabic me 6. `ngettext(singular, plural, count)` use karo; gettext `.po` header ke `Plural-Forms` expression se correct form pick karta hai. English `if` logic doosri languages me galat hoga.

**Q9:** Multi-language site ka URL structure SEO ke liye kaise design karoge?
**A:** URL prefix (`/hi/...` via `i18n_patterns`) best — har language ka unique crawlable URL, single domain authority, `hreflang` alternates + `x-default` lagao, sitemap me sab versions. Subdomain per language possible (django-hosts) par authority split risk. Cookie-only switching public pages pe kabhi nahi — Googlebot cookie nahi bhejta, sirf ek language index hogi.

**Q10:** "Tumne Niroskos me i18n kaise implement kiya?" — model answer skeleton:
**A:** "Platform multi-tenant tha — django-hosts se har tenant ka subdomain. Languages [en + hi — apni real list] support ki. Static UI ke liye standard gettext pipeline: `gettext_lazy` models/forms me, `{% blocktrans %}` templates me, `makemessages`/`compilemessages` CI step me. Language detection: [URL prefix via i18n_patterns / cookie — apna real choice] + custom middleware jo tenant ke `default_language` ko fallback banata tha — order tha tenant-resolution middleware ke baad locale activation. DB content (package names/descriptions) ke liye [extra fields per language / modeltranslation — real choice] kyunki [languages fixed thi, queries simple chahiye thi]. SEO-focused tha to public pages URL-prefixed thi with hreflang tags; Celery emails me `translation.override(user.language)` se user ki language enforce ki. Sabse bada gotcha jo mila: [e.g. fuzzy entries compile nahi hui thi / Celery emails English me ja rahi thi — apna real war story]."

---

## References

- [Django Translation docs](https://docs.djangoproject.com/en/5.2/topics/i18n/translation/)
- [Format localization](https://docs.djangoproject.com/en/5.2/topics/i18n/formatting/)
- [django-modeltranslation](https://django-modeltranslation.readthedocs.io/)
- [django-parler](https://django-parler.readthedocs.io/)
- [Google: Managing multi-regional/multilingual sites (hreflang)](https://developers.google.com/search/docs/specialty/international)
