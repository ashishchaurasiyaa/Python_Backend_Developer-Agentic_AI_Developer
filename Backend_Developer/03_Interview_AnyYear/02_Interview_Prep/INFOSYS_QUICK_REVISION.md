# 🎯 INFOSYS — Python/Django Quick Revision

> **Interview: Saturday 2026-07-25** · Role: Python/Django backend (4 yrs)
> **Kaise use karo:** Day 1 pe poora padho. Friday raat + Saturday subah ko sirf **bold wale "Bolne wala jawab"** skim karo. Har answer ko **bolke** practice karo — likhke nahi.
>
> Source (deep dive): [07_python_tricky_questions.md](07_python_tricky_questions.md) · [Django_DRF index](../../00_Year0-2_Junior/07_Django_DRF/README.md) · [SQL Qs](08_sql_interview_questions.md)

---

## ❌ Pehle: YEH MAT PADHNA (Infosys 4-yr role me nahi aayega)
Metaclasses · Descriptors manual implementation · `asyncio.TaskGroup`/async deadlock · spawn-vs-fork-vs-forkserver · uvloop · ABC-vs-Protocol · py-spy/scalene profiling · multi-tenant architecture · ASGI internals

Time bacha ke **Django ORM** pe lagao — wahi sabse zyada poochha jaata hai.

---

# PART A — Python Gotchas (code dikha ke poochhenge) 🔴

### 1. Mutable default argument ⭐ *(sabse common)*
```python
def f(items=[]):        # ❌
    items.append(1); return items
f()  # [1]    f()  # [1,1]   f()  # [1,1,1]
```
**Bolne wala jawab:** *"Default argument function definition ke time pe ek hi baar evaluate hota hai, har call pe nahi — isliye wahi list share hoti hai. Fix: `items=None` rakho aur andar `if items is None: items = []`."*

### 2. Late binding in closures
```python
funcs = [lambda: i for i in range(3)]
[f() for f in funcs]    # [2,2,2]  — not [0,1,2]
```
**Jawab:** *"`i` lambda ke call time pe lookup hota hai, define time pe nahi. Loop khatam ho chuka hota hai to i=2. Fix: `lambda i=i: i` — default arg se bind kar do."*

### 3. `is` vs `==`
```python
a=256; b=256; a is b   # True
a=257; b=257; a is b   # False
```
**Jawab:** *"CPython chhote integers (-5 se 256) intern karta hai, isliye same object. `is` sirf `None`/`True`/`False`/singletons ke liye — value compare karne ko hamesha `==`."*

### 4. List multiplication trap
```python
m = [[0]*3]*3
m[0][0] = 1      # [[1,0,0],[1,0,0],[1,0,0]]
```
**Jawab:** *"`[[0]*3]*3` ek hi inner list ke 3 reference banata hai. Fix: `[[0]*3 for _ in range(3)]`."*

### 5. Chained comparison
```python
1 < 2 < 3                  # True
False == False == True     # False
```
**Jawab:** *"Chain `and` me expand hota hai: `(False==False) and (False==True)` = False."*

### 6. `+=` vs `x = x + [...]` on list ⭐
```python
def a(x): x += [4]        # mutates caller's list (__iadd__ = in-place)
def b(x): x = x + [4]     # naya list, sirf local name rebind
```
**Jawab:** *"List pe `+=` `__iadd__` call karta hai jo in-place mutate karta hai — caller ko dikhta hai. `x = x + [4]` naya object banata hai. Mutable types ke liye dono equivalent NAHI hain."*

### 7. Single-element tuple
```python
type((1))    # int
type((1,))   # tuple   ← trailing comma
type(())     # tuple
```

### 8. Multiple assignment + mutation
```python
a = b = []
a.append(1)
b            # [1]  — same object
```
**Jawab:** *"`a = b = []` dono naam ek hi list pe point karte hain. 'Do khaali list' banane ke liye alag-alag assign karo."*

### 9. Reference semantics
```python
a = [1,2,3]; b = a
b.append(4); a       # [1,2,3,4] — same list
```
**Jawab:** *"Python me assignment object copy nahi karta, reference banata hai. Copy chahiye to `a.copy()` (shallow) ya `copy.deepcopy(a)` (nested)."*

> **Shallow vs deep copy** — guaranteed question. *"Shallow sirf top level copy karta hai, nested objects abhi bhi shared; deep recursively sab copy karta hai."*

---

# PART B — Python Concepts 🔴

### OOP
- **4 pillars:** Encapsulation (data hide), Inheritance (reuse), Polymorphism (same interface, alag behaviour), Abstraction (detail chhupa ke interface do).
- **MRO / diamond problem:** `class D(B,C)` → `D, B, C, A, object`. *"Python C3 linearization use karta hai — left-to-right, depth-first, duplicates hata ke."*
- **`__new__` vs `__init__`:** *"`__new__` object banata hai (allocation), `__init__` use initialize karta hai. Singleton me `__new__` override karte hain — par dhyan rahe `__init__` har call pe chalta hai."*
- **`@staticmethod` vs `@classmethod`:** *"classmethod ko `cls` milta hai (alternate constructor bana sakte ho), staticmethod ko kuch nahi — bas namespace ke liye class me rakha hota hai."*
- **`__str__` vs `__repr__`:** *"`__str__` end-user ke liye readable, `__repr__` developer/debugging ke liye unambiguous."*

### Decorators ⭐
```python
def my_decorator(func):
    @functools.wraps(func)          # metadata preserve
    def wrapper(*args, **kwargs):
        # before
        result = func(*args, **kwargs)
        # after
        return result
    return wrapper
```
**Jawab:** *"Decorator ek function hai jo function leta hai aur modified function return karta hai — original code change kiye bina behaviour add karta hai. `functools.wraps` isliye lagate hain taaki original ka `__name__`/docstring na khoye. Django me `@login_required` isi ka example hai."*

### Generators ⭐
```python
def gen():
    yield 1; yield 2
```
**Jawab:** *"Generator `yield` use karta hai, saari values memory me nahi rakhta — ek-ek karke lazily deta hai. Badi files/datasets ke liye memory bachaata hai. List saara memory me load karti hai, generator nahi."*
- `range()` vs `list(range())` · `yield` vs `return` · generator expression `(x for x in ...)`

### `*args` / `**kwargs`
*"`*args` extra positional arguments tuple me leta hai, `**kwargs` keyword arguments dict me. Flexible function signature ke liye."*

### Exception handling
```python
try: ...
except ValueError as e: ...
else: ...        # exception nahi aaya to
finally: ...     # hamesha chalega (cleanup)
```
*"Custom exception `Exception` se inherit karke banate hain. Bare `except:` mat likho — specific pakdo."*

### GIL ⭐
**Jawab:** *"GIL ek mutex hai jo ek time pe ek hi thread ko Python bytecode chalane deta hai. IO-bound kaam me problem nahi (IO ke time GIL release hota hai) — CPU-bound multi-threading me problem hai, uske liye `multiprocessing` use karo. Aur `counter += 1` atomic nahi hai (LOAD/ADD/STORE), isliye race condition aa sakti hai."*

### Memory / GC
*"Python primarily reference counting use karta hai; jab count 0 ho object free. Cyclic references (a→b→a) ko refcount nahi pakad sakta, uske liye cycle detector GC hai. `weakref` se cycles avoid karte hain."*

### `list` vs `tuple` vs `set` vs `dict`
| | Mutable | Ordered | Duplicates | Use |
|---|---|---|---|---|
| list | ✅ | ✅ | ✅ | sequence |
| tuple | ❌ | ✅ | ✅ | fixed record, dict key |
| set | ✅ | ❌ | ❌ | uniqueness, fast membership |
| dict | ✅ | ✅ (3.7+) | keys unique | key→value |

### `__slots__` (agar poochhe)
*"`__slots__` `__dict__` hata deta hai — ~40% kam memory, thoda fast attribute access; par dynamically naya attribute nahi jod sakte. Lakhon chhote objects ho tab useful."*

---

# PART C — Django 🔴🔴 *(sabse zyada poochha jaata hai)*

### MVT flow ⭐ — *bolke samjha paana*
*"Request aata hai → URLconf (`urls.py`) usse view pe route karta hai → View business logic chalata hai, Model se DB access karta hai → Template render hota hai → Response wapas. Django MVC ka hi variant hai, bas 'Controller' ka kaam framework khud karta hai, isliye MVT."*

### ORM — QuerySet lazy evaluation ⭐
*"QuerySet lazy hota hai — `Model.objects.filter(...)` likhne pe DB hit nahi hota. Query tab chalti hai jab actually iterate/slice/`list()`/`len()` karo. Isse chaining possible hoti hai bina extra query ke."*

### `select_related` vs `prefetch_related` ⭐⭐ *(guaranteed)*
| | Kab | Kaise |
|---|---|---|
| `select_related` | **ForeignKey / OneToOne** (single-valued) | SQL **JOIN** — ek hi query |
| `prefetch_related` | **ManyToMany / reverse FK** (multi-valued) | **alag query** + Python me join |

**Jawab:** *"N+1 problem tab aati hai jab loop me har object ke liye related object fetch karo. `select_related` ForeignKey ke liye JOIN karke ek query me le aata hai; `prefetch_related` many-to-many ya reverse FK ke liye do query karke Python me match karta hai."*

### N+1 problem ⭐
```python
for book in Book.objects.all():      # 1 query
    print(book.author.name)          # +N queries ❌
Book.objects.select_related('author')  # ✅ 1 query
```

### Migrations
*"`makemigrations` model changes se migration file banata hai, `migrate` usse DB pe apply karta hai. `showmigrations` status dikhata hai, `sqlmigrate` SQL dikhata hai."*

### Middleware ⭐
*"Middleware request/response ke beech ka hook hai — har request pe chalta hai. `MIDDLEWARE` list me **order matter karta hai**: request upar se neeche jaati hai, response neeche se upar aata hai. Example: AuthenticationMiddleware, CSRF, Session."*

### Signals
*"Signals decoupled notification hain — `pre_save`, `post_save`, `pre_delete`, `post_delete`, `m2m_changed`. Model save hone pe kuch aur trigger karna ho to use karte hain. Par overuse mat karo — debugging mushkil ho jaati hai, explicit service function often better."*

### CBV vs FBV
*"FBV simple aur explicit — chhote views ke liye. CBV reusable, inheritance/mixins se DRY — CRUD ke liye `ListView`/`DetailView`/`CreateView` ready-made milte hain."*

### Model relationships
`ForeignKey` (many-to-one) · `OneToOneField` · `ManyToManyField` · `on_delete=CASCADE/PROTECT/SET_NULL` — *"`on_delete` batata hai parent delete hone pe child ka kya ho."*

### `null=True` vs `blank=True`
*"`null` DB level pe NULL allow karta hai; `blank` form/validation level pe khaali allow karta hai. CharField me `null=True` avoid karo — khaali string use karo."*

### QuerySet methods
`filter/exclude/get/all` · `annotate` (per-row aggregate) vs `aggregate` (poore queryset ka) · `Q` objects (OR/complex) · `F` expressions (DB-level, race-free update) · `values()`/`values_list()` · `only()`/`defer()`

### Transactions
*"`@transaction.atomic` block — sab success to commit, koi exception to poora rollback. Paise/inventory jaise operations me zaroori."*

### Caching / other
`cache_page`, low-level cache API, Redis backend · `settings.py` env-based config · `manage.py` custom commands

---

# PART D — DRF

- **Serializer vs ModelSerializer:** *"Serializer me fields manually likhne padte hain; ModelSerializer model se auto-generate karta hai (Django ka ModelForm jaisa)."*
- **APIView vs ViewSet:** *"APIView me HTTP methods (`get`,`post`) khud likhte ho; ViewSet CRUD actions (`list`,`create`,`retrieve`,`update`,`destroy`) deta hai aur Router se URLs auto ban jaate hain."*
- **Authentication vs Permission:** *"Authentication = tu **kaun** hai (Token/JWT/Session). Permission = tu **kya kar sakta** hai (IsAuthenticated, IsAdminUser, custom)."*
- **`serializers.ValidationError`**, `validate_<field>()`, `validate()` — field-level vs object-level validation
- Pagination, filtering, throttling — naam aur ek line kaafi

---

# PART E — SQL (quick)

- **Joins:** INNER (dono me match) · LEFT (left ka sab + match) · RIGHT · FULL
- **`WHERE` vs `HAVING`:** *"`WHERE` grouping se **pehle** rows filter karta hai, `HAVING` `GROUP BY` ke **baad** groups filter karta hai."*
- **Index:** *"Index read fast karta hai, write thoda slow (index bhi update hota hai). B-Tree default."*
- **`DELETE` vs `TRUNCATE` vs `DROP`** · **Normalization** (1NF/2NF/3NF) · **ACID**
- Practice: [08_sql_interview_questions.md](08_sql_interview_questions.md)

---

# PART F — Project Story ⭐ *(Day 5 pe rehearse)*

**Risk:** Tera day job PHP/Laravel/Odoo hai. "Django production experience?" pe atakna nahi hai.

**Honest angle — Odoo = real production Python:**
> *"Mera primary production experience Python me Odoo 17 ke custom modules pe hai — wahan maine ORM models, business logic, aur integrations likhe hain. Odoo ka ORM Django ke ORM se concept-wise kaafi similar hai — models, fields, relations, migrations. Django/DRF maine [apna RAG backend / SaaS project] banate hue deeply use kiya hai, jahan maine [ORM optimization / JWT auth / REST APIs] implement kiye."*

**Rules:**
1. Jhooth mat bolo — "Django mera primary framework nahi tha, par Python production me likha hai" **strong** hai, weak nahi.
2. **STAR format:** Situation → Task → Action → Result (number ke saath: "query time 2s se 200ms").
3. Ek **problem you solved** taiyaar rakho (N+1 fix, slow query, race condition).
4. **5 baar BOLKE practice karo** — likhke nahi. ([English track](../../../english_speaking/README.md))

---

## ✅ Saturday subah — sirf yeh
Part A ke bold jawab · `select_related` vs `prefetch_related` · MVT flow · GIL · decorator/generator · project story ek baar bolke

**Naya kuch mat padhna.** Confidence > cramming. All the best 🚀
