# Django Model Inheritance & Meta Constraints Deep — Abstract/MTI/Proxy, Indexes, DB Constraints

## Why It Matters

Model inheritance ka galat choice = **har query pe hidden JOIN** (multi-table) ya unmaintainable copy-paste (no inheritance). Aur constraints ka game samajhna = data integrity ki **last line of defence** — validators app-level pe race conditions nahi rok sakte, DB constraints rok sakte hain.

Interview reality:
- "TimeStampedModel kaise banaoge bina har model me created_at copy kiye?" → abstract base
- "unique_together deprecated kyun hua?" → UniqueConstraint
- "Do users ne same email se simultaneously signup kiya — validators ke hote hue duplicate kaise ban gaya?" → race condition + DB constraint ka jawab

Yeh file dono cover karti hai: inheritance ke 3 flavors (with traps) + Meta indexes/constraints production-grade.

---

## Core Concepts — Part 1: Model Inheritance DEEP

### 1. Abstract Base Class — `Meta: abstract = True`

**Mechanics:** Parent ki **koi table nahi banti**. Fields child me **copy** ho jaate hain — har child ki apni table me parent ke columns physically hote hain. Pure Python-level reuse.

```python
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Har model me created_at/updated_at chahiye — EK jagah define karo."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True          # ← yahi magic hai — no table for this class


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        # bulk delete bhi soft ho — qs.delete() override
        return super().update(deleted_at=timezone.now())

    def alive(self):
        return self.filter(deleted_at__isnull=True)


class SoftDeleteModel(models.Model):
    """Delete = flag set, row preserved. Audit/recovery ke liye."""
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])

    def hard_delete(self):
        super().delete()         # asli DELETE jab sach me chahiye


# Compose karo — multiple abstract bases theek hain (saare fields merge ho jaate hain)
class Article(TimeStampedModel, SoftDeleteModel):
    title = models.CharField(max_length=200)
    # Table 'article' me: id, title, created_at, updated_at, deleted_at — SAB ek table
```

```sql
-- Sirf EK table banti hai:
CREATE TABLE blog_article (
    id bigint PRIMARY KEY,
    title varchar(200),
    created_at timestamptz,
    updated_at timestamptz,
    deleted_at timestamptz NULL
);
```

**`%(class)s` in related_name — abstract me ForeignKey ho to MUST:**

```python
class Ownable(models.Model):
    owner = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_set',   # ← bina iske clash!
    )

    class Meta:
        abstract = True


class Document(Ownable): ...     # user.blog_document_set
class Invoice(Ownable): ...      # user.blog_invoice_set
```

**Kyun zaroori?** `related_name='items'` hardcode karte to Document aur Invoice **dono** `user.items` claim karte → `makemigrations` pe `fields.E305` clash error. `%(class)s` lowercased child class name se replace hota hai, `%(app_label)s` app name se — har child ko unique reverse accessor mil jaata hai.

**Aur ek subtlety:** child apne abstract parent ke `Meta` ko inherit karta hai (ordering, etc.), but `abstract=True` inherit NAHI hota — child concrete hi banta hai (yahi chahiye bhi). Child apni `Meta` me parent override kar sakta hai.

### 2. Multi-Table Inheritance (MTI) — har class ki apni table

**Mechanics:** Parent concrete hai (apni table), child ki **alag table** with implicit `OneToOneField` named `<parent>_ptr` jo primary key bhi hai.

```python
class Place(models.Model):                  # concrete — table banti hai
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)


class Restaurant(Place):                    # MTI — koi abstract=True NAHI
    serves_pizza = models.BooleanField(default=False)
    # Django implicitly banata hai:
    # place_ptr = models.OneToOneField(Place, parent_link=True,
    #                                  primary_key=True, on_delete=models.CASCADE)
```

```sql
CREATE TABLE place (id bigint PK, name varchar, address varchar);
CREATE TABLE restaurant (
    place_ptr_id bigint PK REFERENCES place(id),   -- PK + FK dono!
    serves_pizza boolean
);
```

**Performance trap — JOIN on EVERY query:**

```python
Restaurant.objects.filter(serves_pizza=True)
# SQL: SELECT ... FROM restaurant
#      INNER JOIN place ON restaurant.place_ptr_id = place.id
#      WHERE serves_pizza = true
# ↑ name/address parent table me hain — JOIN ke bina Restaurant complete hi nahi hota.
# HAR query, HAR save (2 INSERTs/UPDATEs!), HAR fetch — JOIN tax lagta hai.

r = Restaurant.objects.get(pk=1)
r.save()        # DO UPDATE statements — place + restaurant dono tables
```

**Polymorphic queries problem:**

```python
places = Place.objects.all()     # Restaurants BHI aayenge... but as Place instances!
for p in places:
    p.serves_pizza               # ❌ AttributeError — Django nahi jaanta yeh Restaurant hai
    p.restaurant                 # child access possible hai but: extra query + agar yeh
                                 # Restaurant nahi hai to Restaurant.DoesNotExist
# "Saare places do, jo restaurant hain unka restaurant-behavior do" — vanilla Django me painful.
# Solution: django-polymorphic package — PolymorphicModel automatically downcasting karta hai
# (content_type column track karke). But yeh bhi JOINs pe hi chalta hai — magic free nahi hai.
```

**Kab justified (rarely!):** jab tumhe **genuinely parent rows independently chahiye** — e.g. `Event` table me sab events listed hon (calendar view), aur `Conference(Event)`, `Meetup(Event)` apne extra fields rakhein, aur tum parent-level pe FK lagana chahte ho (`Booking.event = FK(Event)` jo kisi bhi event type ko point kare). Agar tum kabhi `Place.objects` directly query nahi karte — MTI galat choice hai, abstract use karo ya explicit OneToOne.

### 3. Proxy Models — same table, different behavior

**Mechanics:** `Meta: proxy = True` → **koi nayi table nahi, koi naya column nahi**. Sirf Python-level wrapper — alag manager, alag methods, alag default ordering, same underlying data.

```python
class Order(models.Model):
    status = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)


class PendingOrderManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status='pending')


class PendingOrder(Order):
    objects = PendingOrderManager()      # default queryset hi filtered

    class Meta:
        proxy = True                     # ← no new table
        ordering = ['created_at']        # FIFO — pending queue jaisa behave kare

    def approve(self):                   # role-specific behavior
        self.status = 'approved'
        self.save(update_fields=['status'])


PendingOrder.objects.all()       # sirf pending — manager ne filter kiya
Order.objects.all()              # sab orders — original untouched
PendingOrder.objects.create(status='pending')   # SAME table me INSERT hota hai
```

**Admin trick — same model ki do alag admin entries:**

```python
# admin.py — Order aur PendingOrder DONO register kar sakte ho.
# Admin sidebar me do entries dikhengi — "Orders" (sab) aur "Pending orders" (queue view),
# alag list_display/actions ke saath. Support team ko sirf PendingOrder do — clean workflow.
@admin.register(PendingOrder)
class PendingOrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'created_at']
    actions = ['approve_selected']
```

**Limitation:** proxy me **naye fields add nahi kar sakte** (table same hai!) — try karoge to error. Sirf behavior change: managers, methods, Meta options.

### 3-Way Comparison Table

| | Abstract Base | Multi-Table (MTI) | Proxy |
|---|---|---|---|
| Parent table? | ❌ Nahi | ✅ Haan | ✅ (wahi ek table) |
| Child table? | ✅ (fields copied) | ✅ (sirf naye fields + ptr) | ❌ Nahi |
| Naye fields child me? | ✅ | ✅ | ❌ Error |
| Query performance | Best (single table) | JOIN har query pe ⚠️ | Same as original |
| Parent ko query kar sakte ho? | ❌ (class hi abstract) | ✅ | ✅ (same data) |
| FK to parent possible? | ❌ | ✅ | ✅ (Order pe hi lagta) |
| save() | 1 statement | 2 statements (dono tables) | 1 statement |
| Use case | Field/behavior reuse (timestamps, soft-delete) | Parent rows independently needed (rare) | Same data, alag behavior/admin/manager |

**Default guidance: abstract use karo.** 90% "inheritance" needs = shared fields/behavior = abstract. MTI tabhi jab parent independently queryable hona business requirement ho — aur tab bhi pehle socho ki explicit `OneToOneField` better to nahi (kam magic, zyada control). Proxy = behavioral variants of same data (admin views, role-specific managers).

---

## Core Concepts — Part 2: Meta Indexes & Constraints DEEP

### models.Index — composite + column order (left-prefix rule!)

```python
class Order(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    status = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            # Composite index — COLUMN ORDER MATTERS!
            models.Index(fields=['user', 'status'], name='order_user_status_idx'),
            # Descending bhi possible — "latest first" queries ke liye
            models.Index(fields=['-created_at'], name='order_created_desc_idx'),
        ]
```

**Left-prefix rule (B-tree index ka fundamental):** `(user, status)` index ek phone book jaisa hai — pehle user se sorted, phir uske andar status se. Isliye:

```python
Order.objects.filter(user=u)                      # ✅ index use hoga (left prefix)
Order.objects.filter(user=u, status='paid')       # ✅ full index use
Order.objects.filter(status='paid')               # ❌ index USELESS — left column missing!
# (Phone book me "sirf first name Rahul" dhundhna — poora book scan karna padega)
```

**Column order decision:** equality-filter wala high-selectivity column pehle. Agar `status` akela bhi filter hota hai frequently → uska **alag** index banao, composite ka order badalne se dono use cases ek index se solve NAHI honge.

**`name=` hamesha do** — Django auto-generate karega warna (truncated hash wala naam), but explicit naam migrations readable aur DB debugging (`EXPLAIN` output, `\di` in psql) me identify karna easy banata hai.

### Partial Index — `condition=Q(...)`

**Real example — soft-delete with active-only uniqueness/lookup:**

```python
from django.db.models import Q


class Subscription(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    plan = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True)

    class Meta:
        indexes = [
            # Index SIRF active rows pe — 95% queries active rows hi maangti hain,
            # aur table me 80% soft-deleted junk pada hai. Index chhota = fast + RAM me fit.
            models.Index(
                fields=['user'],
                name='sub_active_user_idx',
                condition=Q(deleted_at__isnull=True),
            ),
        ]
```

```sql
-- Postgres me yeh banta hai:
CREATE INDEX sub_active_user_idx ON subscription (user_id)
WHERE deleted_at IS NULL;
```

**Catch:** query me **wahi condition match honi chahiye** tabhi planner partial index use karega — `filter(user=u, deleted_at__isnull=True)` ✅, sirf `filter(user=u)` ❌ (planner ko guarantee nahi ki deleted rows nahi chahiye). MySQL partial indexes support **nahi** karta — Postgres/SQLite feature hai.

### Functional Index — expressions pe index

```python
from django.db.models.functions import Lower


class User(models.Model):
    email = models.EmailField()

    class Meta:
        indexes = [
            # Case-insensitive lookup fast karne ke liye
            models.Index(Lower('email'), name='user_email_lower_idx'),
        ]


# Ab yeh query index use karegi:
User.objects.filter(email__iexact='Ashish@Gmail.com')
# Kyunki Postgres me iexact → LOWER(email) = LOWER('...') — aur LOWER(email) pe index hai!
# Bina functional index ke: full table scan, kyunki plain email index LOWER() expression match nahi karta.
```

### db_index vs Meta.indexes

```python
email = models.CharField(max_length=100, db_index=True)   # purana single-column shortcut
```

| | `db_index=True` | `Meta.indexes` |
|---|---|---|
| Single column | ✅ | ✅ |
| Composite / desc / functional / partial | ❌ | ✅ |
| Custom name | ❌ (auto) | ✅ |
| Status | Soft-discouraged (Django 5.1 me deprecation path shuru) | **Preferred** |

**Rule:** naya code `Meta.indexes` use kare — uniform, full-featured, named. Note: `ForeignKey` pe Django **automatically index** banata hai aur `unique=True` bhi index create karta hai — inke upar duplicate `db_index` mat lagao.

### UniqueConstraint — unique_together ka modern replacement

```python
class Enrollment(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    course = models.ForeignKey('Course', on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    email_backup = models.EmailField(null=True)

    class Meta:
        # ❌ OLD (deprecated path): unique_together = [('student', 'course')]
        constraints = [
            # 1. Plain composite unique
            models.UniqueConstraint(
                fields=['student', 'course'],
                name='uniq_student_course',
            ),
            # 2. PARTIAL unique — sirf active enrollments unique hon!
            #    Student course chhod ke (is_active=False) dobara enroll kar sake —
            #    history me multiple inactive rows allowed, active sirf EK.
            #    unique_together se yeh IMPOSSIBLE tha.
            models.UniqueConstraint(
                fields=['student', 'course'],
                condition=Q(is_active=True),
                name='uniq_active_enrollment',
            ),
            # 3. nulls_distinct (Django 5.0+, Postgres 15+)
            #    Default SQL: NULL != NULL → multiple NULL emails allowed.
            #    nulls_distinct=False → sirf EK NULL row allowed.
            models.UniqueConstraint(
                fields=['email_backup'],
                nulls_distinct=False,
                name='uniq_email_backup_one_null',
            ),
        ]
```

**unique_together deprecated kyun?** (docs me "may be deprecated", new code me avoid): UniqueConstraint sab kuch karta hai jo unique_together karta tha PLUS — `condition=` (partial), expressions (`Lower('email')`), `nulls_distinct`, custom `violation_error_message`, aur explicit `name` (migrations me stable reference). Ek hi cheez ke do syntax rakhne ka koi reason nahi.

```python
# Functional unique — case-insensitive unique email (classic requirement!)
models.UniqueConstraint(Lower('email'), name='uniq_email_ci')
# 'Ashish@x.com' aur 'ashish@X.com' dono store NAHI ho sakte
```

### CheckConstraint — row-level business rules DB me

```python
class Payment(models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gte=0),               # Django 5.1+: condition= (pehle check=)
                name='payment_amount_non_negative',
            ),
            models.CheckConstraint(
                condition=Q(discount__lte=models.F('amount')),   # cross-column check!
                name='discount_not_more_than_amount',
            ),
            models.CheckConstraint(
                condition=Q(ends_at__gt=models.F('starts_at')),
                name='ends_after_starts',
            ),
        ]
```

Ab `Payment.objects.create(amount=-50)` → **IntegrityError** — chahe ORM se aaye, raw SQL se, `bulk_create` se, ya kisi doosre service se jo same DB share karta hai. **Validators sirf Django forms/serializers ke raste rokte hain; CheckConstraint har raasta rokta hai.**

### DB Constraints vs App-Level Validators — race condition ka sach

**Yeh interview ka favorite hai.** Scenario: email unique chahiye, sirf validator lagaya:

```
Request A (t=0ms): SELECT ... WHERE email='x@y.com'  → not found → validation PASS
Request B (t=2ms): SELECT ... WHERE email='x@y.com'  → not found → validation PASS  (A ne abhi INSERT nahi kiya!)
Request A (t=5ms): INSERT ... ✅
Request B (t=7ms): INSERT ... ✅ ← DUPLICATE! Validator helpless tha.
```

**Kyun validators se nahi rukti:** validation aur insert ke beech **time gap** hai (check-then-act), aur do requests parallel processes/threads me chal rahe hain. App-level pe is gap ko close karne ka koi reliable tarika nahi (lock lagao to bhi multi-server me distributed lock chahiye — overkill). **DB constraint atomic hai** — INSERT ke moment pe DB khud check karta hai, race window zero.

**Sahi pattern: dono layers + IntegrityError handle karo:**

```python
from django.db import IntegrityError


def register_user(email: str):
    try:
        return User.objects.create(email=email)
    except IntegrityError as e:
        # Constraint NAME se identify karo kaunsa toota (isliye naam dena zaroori tha!)
        if 'uniq_email_ci' in str(e):
            raise ValidationError({'email': 'Email already registered.'})
        raise   # koi aur constraint — bubble up, swallow mat karo


# Django 4.1+: full_clean() constraints ko bhi validate karta hai (best-effort, pre-save) —
# forms me friendly error pehle hi mil jaata hai. But race ke against guarantee SIRF DB deta hai.
# Layered approach: validator = good UX (early, friendly error), constraint = correctness.
```

### Migration Behavior — AddIndex + Postgres concurrent

```python
# makemigrations generates:
migrations.AddIndex(
    model_name='order',
    index=models.Index(fields=['user', 'status'], name='order_user_status_idx'),
)
# Problem: Postgres me normal CREATE INDEX table pe WRITE LOCK leta hai —
# badi table (50M rows) pe minutes tak saare INSERT/UPDATE blocked. Production outage!
```

```python
# Fix: Postgres-only — CREATE INDEX CONCURRENTLY (writes block nahi hote)
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False    # ← ZAROORI — CONCURRENTLY transaction ke andar nahi chal sakta

    dependencies = [('shop', '0042_previous')]

    operations = [
        AddIndexConcurrently(
            model_name='order',
            index=models.Index(fields=['user', 'status'], name='order_user_status_idx'),
        ),
    ]
```

**Notes:** (1) `atomic = False` ke bina `CREATE INDEX CONCURRENTLY cannot run inside a transaction block` error; (2) concurrently slow hota hai aur fail ho sakta hai (invalid index chhod ke — manually drop karna padta hai), but **zero downtime**; (3) `RemoveIndexConcurrently` bhi hai; (4) constraints add karna bhi lock leta hai — bade table pe `NOT VALID` + `VALIDATE CONSTRAINT` two-step pattern (raw SQL migration) use hota hai. Detail file 25 (zero_downtime_migrations) me.

---

## Common Pitfalls

### 1. Abstract base me hardcoded related_name

```python
class Ownable(models.Model):
    owner = models.ForeignKey(User, related_name='items', ...)   # ❌ do children = E305 clash
    class Meta:
        abstract = True
# ✅ related_name='%(app_label)s_%(class)s_set'
```

### 2. MTI accidentally — abstract=True bhoolna

```python
class BaseModel(models.Model):       # abstract=True likhna bhool gaye
    created_at = models.DateTimeField(auto_now_add=True)

class Article(BaseModel): ...
# Ab BaseModel ki TABLE ban gayi + har Article query me JOIN + har save me 2 INSERTs.
# Migration dekho — do CreateModel aaye to red flag!
```

### 3. Proxy model me naya field

```python
class PendingOrder(Order):
    priority = models.IntegerField()    # ❌ FieldError — proxy me fields NAHI
    class Meta:
        proxy = True
```

### 4. Composite index ka galat column order

`Index(fields=['status', 'user'])` banaya, but queries `filter(user=u)` karti hain → left-prefix rule ke kaaran index **kabhi use nahi hoga**. `EXPLAIN ANALYZE` se verify karo, andaaze se index mat banao.

### 5. Partial index but query me condition nahi

Index `condition=Q(deleted_at__isnull=True)` ke saath banaya, but query sirf `filter(user=u)` hai → planner partial index skip karega. Query me bhi `deleted_at__isnull=True` lagao (custom manager me bake kar do — `objects = ActiveManager()`).

### 6. IntegrityError ko swallow karna

```python
try:
    obj.save()
except IntegrityError:
    pass    # ❌ kaunsa constraint toota? User ko kya bataye? Data silently lost!
# ✅ Constraint name check karke specific friendly error, warna re-raise.
```

### 7. Constraint without name

Pehle Django auto-names deta tha jo cryptic hote the; ab `name=` required hai UniqueConstraint/CheckConstraint me — but log `name='uniq1'` jaisa garbage dete hain. **Naam = error handling ka API** (`if 'uniq_email_ci' in str(e)`) — descriptive rakho.

### 8. Badi table pe plain AddIndex deploy karna

50M rows wali table pe normal `AddIndex` migration → write lock → production me checkout/orders freeze. Postgres pe `AddIndexConcurrently` + `atomic = False`. Deploy se pehle migration review me yeh check karna senior habit hai.

### 9. Soft-delete model me unique constraint bina condition

`UniqueConstraint(fields=['email'])` + soft delete = user delete hua, dobara same email se signup → IntegrityError (purani soft-deleted row clash kar rahi)! Fix: `condition=Q(deleted_at__isnull=True)` — uniqueness sirf alive rows pe.

---

## Interview Q&A

**Q1:** Django me model inheritance ke 3 types aur unka table-level difference?
**A:** (1) **Abstract** (`abstract=True`) — parent ki table nahi, fields child tables me copy. (2) **Multi-table** — parent + child dono tables, child me implicit `parent_ptr` OneToOne (PK+FK), har query pe JOIN. (3) **Proxy** (`proxy=True`) — koi nayi table nahi, same data pe alag Python behavior (manager/methods/ordering). Default: abstract — single table, best performance.

**Q2:** TimeStampedModel kaise banaoge?
**A:** Abstract base: `created_at = DateTimeField(auto_now_add=True)`, `updated_at = DateTimeField(auto_now=True)`, `Meta: abstract=True`. Har model isse inherit kare — fields har child ki apni table me aate hain, koi JOIN nahi. Soft-delete bhi isi pattern se (deleted_at + custom QuerySet jiska delete() update karta hai). Multiple abstract bases compose ho sakte hain.

**Q3:** MTI performance trap kya hai? Kab justified?
**A:** Child ka data do tables me split hota hai — **har query me INNER JOIN**, har save me 2 statements. Polymorphic problem bhi: `Place.objects.all()` me Restaurant rows Place instances ke roop me aate hain — child fields ke liye extra query/downcasting (django-polymorphic isko solve karta hai but JOINs rehte hain). Justified rarely — jab parent rows independently queryable hona business need ho (calendar me sab Events) ya parent pe FK chahiye. Warna abstract ya explicit OneToOne.

**Q4:** `%(class)s` in related_name kyun?
**A:** Abstract base me FK ho aur related_name hardcoded ho to har child same reverse accessor claim karega → `fields.E305` clash. `related_name='%(app_label)s_%(class)s_set'` me Django child ke naam se placeholder replace karta hai — `user.blog_document_set`, `user.blog_invoice_set` — har child unique.

**Q5:** Proxy model real use case?
**A:** Same table, alag behavior: (1) admin me do entries — `Order` (full) + `PendingOrder` (filtered manager + queue ordering + approve action) support team ke liye; (2) role-specific managers (`PublishedPost.objects` default-filtered); (3) alag default ordering. Limitation: naye fields add nahi kar sakte — table same hai.

**Q6:** Composite index me column order kyun matter karta hai?
**A:** B-tree left-prefix rule — `(user, status)` index pehle user se sorted hai. `filter(user=...)` aur `filter(user=..., status=...)` index use karenge; akela `filter(status=...)` NAHI (left column missing — phone book me sirf first name dhundhne jaisa). Order decide karo most-common equality filter + selectivity se; alag standalone queries ke liye alag index.

**Q7:** Partial index kya hai, kab use karoge?
**A:** `models.Index(..., condition=Q(...))` — index sirf matching rows pe banta hai (Postgres `WHERE` clause index). Classic: soft-delete table me 80% dead rows — `condition=Q(deleted_at__isnull=True)` se index chhota, hot data RAM me, writes pe maintenance kam. Catch: query me condition match honi chahiye tabhi planner use karta hai. Partial **unique** bhi: sirf active enrollment unique ho, inactive history duplicates allowed.

**Q8:** unique_together vs UniqueConstraint?
**A:** `unique_together` legacy hai (docs: may be deprecated). `UniqueConstraint` superset: `condition=` (partial unique), expressions (`Lower('email')` — case-insensitive unique), `nulls_distinct=False` (Django 5.0, Postgres 15 — ek hi NULL allowed), explicit `name`, custom violation message. Naya code hamesha `Meta.constraints` me UniqueConstraint.

**Q9:** Validators ke hote hue duplicate row kaise ban gayi? (race condition)
**A:** Validator check-then-act hai: SELECT (exists?) → INSERT ke beech gap me doosri request bhi SELECT pass kar leti hai → dono INSERT → duplicate. App level pe yeh gap close nahi hota (multi-server me to bilkul nahi). DB UniqueConstraint atomic hai — INSERT moment pe enforce, race window zero. Pattern: validator for UX (friendly early error) + constraint for correctness + `IntegrityError` catch karke constraint name se friendly message map karo.

**Q10:** Production me badi table pe index add karna — kya dhyan rakhoge?
**A:** Postgres me normal `CREATE INDEX` write-lock leta hai — badi table pe minutes ka write freeze. Fix: `AddIndexConcurrently` (django.contrib.postgres.operations) + migration class me `atomic = False` (CONCURRENTLY transaction me nahi chalta). Slow hai aur fail hone pe invalid index chhod sakta hai (manual drop), but zero downtime. Constraints ke liye `NOT VALID` + `VALIDATE` two-step. MySQL me online DDL / gh-ost / pt-online-schema-change.

---

## Real-World Use Cases

### 1. SaaS base models stack

```python
class BaseModel(TimeStampedModel, SoftDeleteModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True
# Har tenant-facing model isse inherit — timestamps + soft-delete + UUID PK, zero repetition.
```

### 2. Payments table — constraints as safety net

```python
class Meta:
    constraints = [
        models.CheckConstraint(condition=Q(amount__gt=0), name='pay_amount_positive'),
        models.UniqueConstraint(
            fields=['idempotency_key'],
            condition=Q(status__in=['pending', 'success']),
            name='uniq_active_idempotency_key',     # retry-safe payment API ka core!
        ),
    ]
# Gateway webhook duplicate aaya → second INSERT IntegrityError → catch → existing return.
# Yeh idempotency DB-level guarantee hai — app crash ho ya 3 workers parallel hon, double-charge impossible.
```

### 3. Case-insensitive unique username + fast lookup

```python
class Meta:
    constraints = [models.UniqueConstraint(Lower('username'), name='uniq_username_ci')]
    indexes = [models.Index(Lower('username'), name='username_lower_idx')]
# Signup pe 'Ashish' vs 'ashish' clash blocked + login me iexact lookup indexed.
```

---

## Bonus: CompositePrimaryKey (Django 5.2+)

Django 5.2 ka headline ORM feature — ab tak har model me single-column PK (auto `id`) compulsory tha; ab composite natural keys natively:

```python
from django.db import models

class OrderItem(models.Model):
    pk = models.CompositePrimaryKey("order_id", "product_id")   # field ka naam 'pk' hi hona chahiye
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()

# Lookups tuple se:
OrderItem.objects.get(pk=(42, 7))
item.pk          # → (42, 7)
```

**Kab use karo:** junction/association tables (order_items, enrollments), multi-tenant row keys (`tenant_id + local_id`), legacy DB integration jahan composite PK pehle se hai (`inspectdb` ab inhe detect karta hai).

**Limitations (yehi interview me poochte hain):**
```
1. Doosre models se is model pe ForeignKey NAHI kar sakte abhi —
   composite FK support future release me hai. Isliye "children" wale
   models ke liye ab bhi surrogate id + UniqueConstraint pattern sahi hai.
2. Field ka naam literally `pk` hona zaroori hai.
3. DRF/admin tooling tuple-pk se URLs banate time friction dega —
   API-facing models pe surrogate key + composite UNIQUE constraint
   ab bhi zyada practical hai.
```

**Interview line:** *"5.2 se pehle composite natural key = surrogate `id` + `UniqueConstraint(fields=[...])`. 5.2 me `CompositePrimaryKey` native hai — main junction tables aur legacy schemas ke liye use karta hoon, par jis model pe doosre models FK karte hain wahan surrogate hi rakhta hoon kyunki composite-FK abhi supported nahi."*

---

## References

- [Model inheritance](https://docs.djangoproject.com/en/5.0/topics/db/models/#model-inheritance)
- [Constraints reference](https://docs.djangoproject.com/en/5.0/ref/models/constraints/)
- [Model index reference](https://docs.djangoproject.com/en/5.0/ref/models/indexes/)
- [Postgres operations (AddIndexConcurrently)](https://docs.djangoproject.com/en/5.0/ref/contrib/postgres/operations/)
- [django-polymorphic](https://django-polymorphic.readthedocs.io/) — MTI polymorphic queries
- [Use the Index, Luke — left-prefix](https://use-the-index-luke.com/sql/where-clause/the-equals-operator/concatenated-keys)
