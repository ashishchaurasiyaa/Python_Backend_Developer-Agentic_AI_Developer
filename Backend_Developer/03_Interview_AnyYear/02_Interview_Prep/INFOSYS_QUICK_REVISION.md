# 🎯 INFOSYS — Python/Django Quick Revision

> **Interview: Saturday 2026-07-25** · Role: Python/Django backend (4 yrs)
>
> ## 📖 Is file ko kaise use karna hai
> Har topic ke do hisse hain:
> - **Samajh (Hinglish)** — concept detail me samajhne ke liye. Yeh sirf *tere liye* hai.
> - **💬 Say this (English)** — **exact sentence jo interview me bolna hai.** Ise **awaaz me, 3–5 baar** bolo. Ratta nahi — flow aana chahiye.
>
> **Niyam:** Samajh Hinglish me karo, jawab hamesha English me practice karo. Interview me Hinglish translate karne ki koshish mat karna — wahi atakne ka main reason hota hai.
>
> Deep dive: [07_python_tricky_questions.md](07_python_tricky_questions.md) · [Django_DRF index](../../00_Year0-2_Junior/07_Django_DRF/README.md) · [SQL Qs](08_sql_interview_questions.md)

---

## ❌ Pehle: YEH MAT PADHNA
Metaclasses · Descriptors manual implementation · async deadlock / `TaskGroup` · spawn-vs-fork-vs-forkserver · uvloop · ABC-vs-Protocol · py-spy/scalene · multi-tenant architecture · ASGI internals

**Infosys 4-year role me yeh nahi aayega.** Bacha hua time **Django ORM** pe lagao.

---

## 🗣️ Interview English — 6 ready-made phrases

Yeh phrases har jawab me kaam aayenge. Inhe pehle ratt lo:

| Situation | English phrase |
|---|---|
| Answer shuru karna | *"Sure. So basically, …"* / *"Right — the way I understand it, …"* |
| Example dena | *"For example, in my project I …"* |
| Compare karna | *"The main difference is that …"* |
| Nahi aata | *"I haven't worked with that directly, but my understanding is …"* |
| Sochne ka time | *"That's a good question — let me think for a second."* |
| Confirm karna | *"Does that answer your question?"* |

> ⚠️ **"I don't know" bolna galat nahi hai** — bhagna galat hai. Honest + reasoning dikhana strong lagta hai.

---

# PART 0 — Warm-Up Questions 🔴 *(round ki shuruaat me yahi aate hain)*

> **Research finding:** Infosys ke reported interviews me technical round **"medium-to-easy"** hota hai aur shuruaat in basic sawaalon se hoti hai. Inhe halka mat samajhna — pehla impression yahin banta hai. In sab ka jawab **fluent English me** aana chahiye.

### 1. Is Python interpreted or compiled? ⭐ *(bahut baar poochha gaya)*
**Samajh:** Dono thoda-thoda. Python source code pehle **bytecode** me compile hota hai (woh `.pyc` files jo `__pycache__` me dikhti hain), phir **PVM (Python Virtual Machine)** us bytecode ko interpret karke chalata hai. Isliye technically Python "interpreted" kehlata hai, par beech me ek compilation step hai.

**💬 Say this:**
> *"Python is technically both. The source code is first compiled into bytecode, which is stored in the `__pycache__` folder, and then the Python Virtual Machine interprets that bytecode line by line. So there is a compilation step, but since we don't compile to machine code ahead of time, Python is generally called an interpreted language."*

---

### 2. Why Python? What are its features? ⭐
**Samajh:** Simple aur readable syntax, dynamically typed, huge standard library, cross-platform, aur bahut strong ecosystem (Django/DRF web ke liye, pandas/numpy data ke liye). Development speed bahut fast hai.

**💬 Say this:**
> *"Python has a very simple and readable syntax, so development is fast and the code is easy to maintain. It is dynamically typed, cross-platform, and has a huge standard library. It also has a strong ecosystem — Django and DRF for web development, and pandas and NumPy for data work. That combination is why it is a good fit for backend development."*

---

### 3. Mutable vs Immutable ⭐
**Samajh:** **Mutable** = banne ke baad badal sakte ho (`list`, `dict`, `set`). **Immutable** = nahi badal sakte (`int`, `float`, `str`, `tuple`, `frozenset`). Immutable objects hi dict ke key ban sakte hain, kyunki unka hash kabhi badalta nahi.

**💬 Say this:**
> *"Mutable objects can be changed after creation — like lists, dictionaries, and sets. Immutable objects cannot be changed — like strings, tuples, and integers. One practical consequence is that only immutable objects can be used as dictionary keys, because their hash value never changes."*

---

### 4. Class vs Object, and constructor ⭐
**Samajh:** **Class** ek blueprint hai; **object** us blueprint se bana actual instance. `__init__` Python ka constructor hai — object banne ke **baad** use initialize karta hai (actual allocation `__new__` karta hai). `self` current instance ko refer karta hai.

**💬 Say this:**
> *"A class is a blueprint that defines attributes and methods, and an object is an actual instance created from that class. `__init__` is the constructor — it runs when the object is created and initialises its attributes. The `self` parameter refers to the current instance, which is how each object keeps its own data."*

---

### 5. Multiple inheritance ⭐
**Samajh:** Ek class do ya zyada parent classes se inherit kar sakti hai. Agar dono parents me same method ho to Python **MRO (C3 linearization)** se decide karta hai kis ka chalega — left se right. Yahi diamond problem ka solution hai.

**💬 Say this:**
> *"In multiple inheritance, a class inherits from more than one parent class. If the same method exists in more than one parent, Python decides which one to use through the Method Resolution Order, which follows C3 linearization from left to right. That is how Python handles the diamond problem."*

---

### 6. What is PEP 8?
**Samajh:** Python ka official **style guide** — naming conventions, indentation (4 spaces), line length, imports ka order. Team me consistent code ke liye. Tools: `flake8`, `black`, `ruff`.

**💬 Say this:**
> *"PEP 8 is the official style guide for Python. It covers things like four-space indentation, naming conventions, and import ordering. Following it keeps the codebase consistent across a team, and we usually enforce it automatically with tools like flake8 or black."*

---

### 7. How is memory managed in Python?
**💬 Say this:**
> *"Python manages memory automatically using reference counting — when an object's reference count reaches zero, the memory is released. It also has a garbage collector to handle cyclic references, which reference counting alone cannot free. All of this happens in a private heap managed by the interpreter."*

---

### 8. Quick-fire (ek line me jawab taiyaar rakho)
| Question | 💬 English answer |
|---|---|
| `list` vs `tuple`? | *"A list is mutable, a tuple is immutable — so a tuple can be a dictionary key."* |
| `is` vs `==`? | *"`==` compares values, `is` compares identity."* |
| `append` vs `extend`? | *"`append` adds one element; `extend` adds each item of an iterable."* |
| `range` vs `xrange`? | *"In Python 3, `range` is already lazy — `xrange` was the Python 2 version."* |
| Shallow vs deep copy? | *"Shallow copies only the top level; deep copy copies everything recursively."* |
| What is `self`? | *"It refers to the current instance of the class."* |
| Python 2 vs 3? | *"Python 3 has proper Unicode strings, `print` as a function, and integer division changes. Python 2 is end-of-life."* |

---

# PART A — Python Gotchas (code dikha ke poochhenge) 🔴

### 1. Mutable default argument ⭐ *(sabse common)*
```python
def f(items=[]):        # ❌
    items.append(1); return items
f()  # [1]    f()  # [1,1]   f()  # [1,1,1]
```
**Samajh:** Python me default argument function **define hone ke time pe ek hi baar** evaluate hota hai — har call pe naya nahi banta. To wahi ek list saare calls me share hoti rehti hai, aur values जुड़ती jaati hain. Yeh bug Django views aur cache decorators me bahut aata hai.

**💬 Say this:**
> *"Default arguments in Python are evaluated only once, at function definition time — not on every call. So the same list object is shared across all calls, and the values keep accumulating. The fix is to use `None` as the default and create a new list inside the function."*

---

### 2. Late binding in closures
```python
funcs = [lambda: i for i in range(3)]
[f() for f in funcs]    # [2,2,2]  — not [0,1,2]
```
**Samajh:** Lambda ke andar `i` **call ke time** pe lookup hota hai, define ke time pe nahi. Jab tak tu `f()` call karta hai, loop khatam ho chuka hota hai aur `i` ki value 2 hai. Isliye teeno 2 dete hain.

**💬 Say this:**
> *"This is late binding. The variable `i` is looked up when the lambda is called, not when it is defined. By the time we call the functions, the loop has finished and `i` is 2. We fix it by binding the value as a default argument — `lambda i=i: i`."*

---

### 3. `is` vs `==` ⭐
```python
a = 256; b = 256; a is b   # True
a = 257; b = 257; a is b   # False
```
**Samajh:** `==` **value** compare karta hai, `is` **identity** (memory me same object hai ya nahi). CPython performance ke liye chhote integers (-5 se 256) pehle se cache karke rakhta hai, isliye 256 pe same object milta hai aur 257 pe nahi.

**💬 Say this:**
> *"`==` compares values, while `is` compares identity — whether both names point to the same object in memory. CPython caches small integers from minus five to 256, so they return the same object. As a rule, I use `is` only for `None`, `True`, `False`, and singletons, and `==` for actual value comparison."*

---

### 4. List multiplication trap
```python
m = [[0]*3]*3
m[0][0] = 1      # [[1,0,0],[1,0,0],[1,0,0]]
```
**Samajh:** `[[0]*3]*3` teen alag lists nahi banata — **ek hi list ke teen reference** banata hai. Isliye ek row badalne pe teeno badal jaati hain.

**💬 Say this:**
> *"The multiplication creates three references to the same inner list, not three separate lists. So changing one row changes all of them. The correct way is a list comprehension — `[[0]*3 for _ in range(3)]` — which creates a new list each time."*

---

### 5. `+=` vs `x = x + [...]` on lists ⭐
```python
def a(x): x += [4]        # caller ki list mutate hoti hai
def b(x): x = x + [4]     # naya object, caller unaffected
```
**Samajh:** List pe `+=` andar se `__iadd__` call karta hai jo list ko **in-place mutate** karta hai (`extend` jaisa) — isliye caller ko change dikhta hai. `x = x + [4]` ek **naya** list banata hai aur sirf local naam rebind karta hai. Mutable types ke liye dono **equivalent nahi** hain.

**💬 Say this:**
> *"For lists, `+=` calls `__iadd__`, which modifies the list in place, so the caller sees the change. But `x = x + [4]` creates a completely new list and only rebinds the local variable, so the caller's list stays unchanged. For mutable types the two are not equivalent."*

---

### 6. Chained comparison
```python
1 < 2 < 3                  # True
False == False == True     # False
```
**Samajh:** Python chain ko `and` me expand karta hai. `False == False == True` ka matlab `(False == False) and (False == True)` = `True and False` = `False`.

**💬 Say this:**
> *"Python expands chained comparisons using `and`. So this becomes `False == False` and `False == True`, which is `True and False`, giving `False`."*

---

### 7. Single-element tuple
```python
type((1))    # int      ← sirf brackets
type((1,))   # tuple    ← trailing comma
```
**Samajh:** Tuple ko **comma** banata hai, brackets nahi. `(1)` sirf grouping hai.

**💬 Say this:**
> *"In Python it is the comma that makes a tuple, not the parentheses. `(1)` is just a grouped integer, while `(1,)` with a trailing comma is a tuple."*

---

### 8. Reference semantics + copy ⭐
```python
a = [1,2,3]; b = a
b.append(4); a       # [1,2,3,4] — same list
```
**Samajh:** Python me assignment object ko **copy nahi karta** — bas ek aur naam usi object pe point karne lagta hai. Copy chahiye to explicitly banao.
- **Shallow copy** (`a.copy()`, `list(a)`) — sirf top level copy, andar ke nested objects abhi bhi shared
- **Deep copy** (`copy.deepcopy(a)`) — recursively sab kuch naya

**💬 Say this:**
> *"Assignment in Python does not copy the object — it just creates another reference to the same object, so changes are visible through both names. If I need a copy, a shallow copy duplicates only the top level and still shares the nested objects, while `deepcopy` recursively copies everything."*

---

# PART B — Python Concepts 🔴

### OOP — 4 pillars
**Samajh:** **Encapsulation** — data aur uspe kaam karne wale methods ek class me bandh karo, andar ka detail bahar mat dikhao. **Inheritance** — existing class se properties/methods inherit karke reuse karo. **Polymorphism** — same method naam, alag-alag class me alag behaviour. **Abstraction** — implementation chhupa ke sirf zaroori interface expose karo.

**💬 Say this:**
> *"There are four main principles. Encapsulation means bundling data and the methods that work on it inside a class and hiding the internal details. Inheritance lets a class reuse the properties and methods of a parent class. Polymorphism means the same method name can behave differently in different classes. And abstraction means exposing only what is necessary and hiding the implementation."*

---

### MRO / diamond problem
```python
class A: pass
class B(A): pass
class C(A): pass
class D(B, C): pass
D.__mro__   # (D, B, C, A, object)
```
**Samajh:** Jab multiple inheritance ho, Python ko decide karna padta hai ki method kis class me pehle dhoondhe. Iske liye **C3 linearization** algorithm use hota hai — left se right, depth-first, aur duplicate hata ke.

**💬 Say this:**
> *"MRO stands for Method Resolution Order — it decides the order in which Python looks for a method in multiple inheritance. Python uses C3 linearization, which goes left to right, depth first, and removes duplicates. That is how Python solves the diamond problem."*

---

### Decorators ⭐
```python
def my_decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # before
        result = func(*args, **kwargs)
        # after
        return result
    return wrapper
```
**Samajh:** Decorator ek function hai jo doosre function ko input leta hai aur ek modified function return karta hai — **original code ko chhue bina** behaviour add karta hai (logging, auth, caching, timing). `functools.wraps` isliye lagate hain taaki original function ka `__name__` aur docstring na kho jaaye. Django ka `@login_required` isi ka example hai.

**💬 Say this:**
> *"A decorator is a function that takes another function and returns a modified version of it. It lets me add behaviour like logging, authentication, or caching without changing the original function's code. I use `functools.wraps` so the original function's name and docstring are preserved. A common example in Django is the `login_required` decorator."*

---

### Generators ⭐
```python
def gen():
    yield 1
    yield 2
```
**Samajh:** Normal function `return` pe khatam ho jaata hai; generator `yield` pe **ruk jaata hai aur apni state yaad rakhta hai**. Saari values ek saath memory me nahi aatin — ek-ek karke **lazily** milti hain. Badi files ya lakhon rows process karne me memory bahut bachti hai.

**💬 Say this:**
> *"A generator uses `yield` instead of `return`. It does not build the whole result in memory — it produces values one at a time and remembers its state between calls. So for large files or large datasets it saves a lot of memory, whereas a list would load everything at once."*

---

### `*args` / `**kwargs`
**Samajh:** `*args` extra **positional** arguments ko tuple me collect karta hai, `**kwargs` extra **keyword** arguments ko dict me. Isse function flexible ban jaata hai.

**💬 Say this:**
> *"`*args` collects extra positional arguments as a tuple, and `**kwargs` collects extra keyword arguments as a dictionary. I use them when a function needs to accept a flexible number of arguments."*

---

### Exception handling
```python
try:      ...
except ValueError as e: ...
else:     ...    # exception nahi aaya to
finally:  ...    # hamesha (cleanup)
```
**Samajh:** `except` specific exception pakdo — bare `except:` mat likho, woh real bugs chhupa deta hai. `else` tab chalta hai jab koi exception na aaye. `finally` hamesha chalta hai — file/connection close karne ke liye. Custom exception `Exception` se inherit karke banate hain.

**💬 Say this:**
> *"I always catch specific exceptions rather than using a bare `except`, because a bare except hides real bugs. The `else` block runs when no exception occurred, and `finally` always runs, so I use it for cleanup like closing a file or a database connection."*

---

### GIL ⭐
**Samajh:** GIL (Global Interpreter Lock) ek mutex hai jo ensure karta hai ki **ek time pe sirf ek thread Python bytecode chalaye**. IO-bound kaam (network call, file read, sleep) me GIL **release** ho jaata hai — isliye threading wahan faayda deti hai. CPU-bound kaam me threading se koi speed nahi milti, wahan `multiprocessing` chahiye. Aur `counter += 1` atomic nahi hai (LOAD, ADD, STORE — teen steps), isliye race condition ho sakti hai.

**💬 Say this:**
> *"The GIL is a lock that allows only one thread to execute Python bytecode at a time. For I/O-bound work the GIL is released during the I/O operation, so threading still helps. But for CPU-bound work threading does not give real parallelism, so I would use multiprocessing instead. Also, an operation like `counter += 1` is not atomic — it is several bytecode steps — so it can still cause a race condition."*

---

### Memory & Garbage Collection
**Samajh:** Python mainly **reference counting** use karta hai — jaise hi object ka count 0 hua, memory free. Problem: **cyclic reference** (a→b→a) me count kabhi 0 nahi hota, isliye ek alag **cycle detector GC** hai jo aise cycles dhoondh ke free karta hai. Cycles avoid karne ke liye `weakref` use karte hain.

**💬 Say this:**
> *"Python mainly uses reference counting — when an object's reference count drops to zero, it is freed immediately. But reference counting cannot handle cyclic references, where two objects point to each other, so Python also has a cycle-detecting garbage collector for those. To avoid cycles I can use weak references."*

---

### `list` vs `tuple` vs `set` vs `dict`
| | Mutable | Ordered | Duplicates | Use |
|---|---|---|---|---|
| list | ✅ | ✅ | ✅ | general sequence |
| tuple | ❌ | ✅ | ✅ | fixed record, dict key ban sakta hai |
| set | ✅ | ❌ | ❌ | uniqueness, fast membership check |
| dict | ✅ | ✅ (3.7+) | keys unique | key → value mapping |

**💬 Say this:**
> *"A list is mutable and ordered. A tuple is immutable, so it can be used as a dictionary key. A set stores only unique values and gives very fast membership checks. And a dictionary stores key-value pairs, with unique keys."*

---

# PART C — Django 🔴🔴 *(sabse zyada poochha jaata hai)*

### MVT flow ⭐ — *bolke samjha paana zaroori*
**Samajh:** Request aata hai → `urls.py` (URLconf) usse sahi **View** pe bhejta hai → View business logic chalata hai aur **Model** ke through DB se data leta hai → **Template** me data render hota hai → Response wapas jaata hai. Django MVC ka hi variant hai; bas "Controller" ka kaam framework khud kar deta hai, isliye ise MVT kehte hain.

**💬 Say this:**
> *"When a request comes in, Django's URL configuration maps it to a view. The view contains the business logic and uses the model to interact with the database. Then the template renders the data into HTML and the response goes back to the user. It is similar to MVC, but Django itself handles the controller part, so it is called MVT."*

---

### QuerySet lazy evaluation ⭐
**Samajh:** `Model.objects.filter(...)` likhne pe DB pe **koi query nahi jaati**. QuerySet lazy hota hai — query tab chalti hai jab tu actually data maange: iterate karo, `list()` karo, `len()` karo, ya slice karo. Isi wajah se filters chain kar sakte ho bina extra query ke.

**💬 Say this:**
> *"Django QuerySets are lazy. Just writing a filter does not hit the database — the query is executed only when the data is actually needed, for example when I iterate over it, convert it to a list, or take its length. This is what allows me to chain multiple filters without making extra queries."*

---

### `select_related` vs `prefetch_related` ⭐⭐ *(guaranteed question)*
| | Kab use karo | Kaise kaam karta hai |
|---|---|---|
| `select_related` | **ForeignKey / OneToOne** (single object) | SQL **JOIN** — sab ek hi query me |
| `prefetch_related` | **ManyToMany / reverse FK** (multiple objects) | **alag query** + Python me match |

**Samajh:** Dono N+1 problem solve karte hain, par alag tarike se. `select_related` SQL JOIN karke related row usi query me le aata hai — isliye sirf single-valued relations (FK, OneToOne) pe chalta hai. `prefetch_related` ek doosri query maarta hai aur phir Python me dono ko jod deta hai — isliye many-valued relations (M2M, reverse FK) ke liye.

**💬 Say this:**
> *"Both are used to avoid the N+1 query problem, but they work differently. `select_related` uses a SQL join and fetches the related object in the same query, so it works for foreign key and one-to-one relations. `prefetch_related` runs a separate query and joins the results in Python, so it is used for many-to-many and reverse foreign key relations."*

---

### N+1 problem ⭐
```python
for book in Book.objects.all():      # 1 query
    print(book.author.name)          # + N queries  ❌
Book.objects.select_related('author')  # ✅ 1 query
```
**Samajh:** Pehli query saare books laati hai, phir **har book ke liye** ek alag query author ke liye chalti hai — 100 books = 101 queries. Yeh production me sabse common performance bug hai. Detect karne ke liye Django Debug Toolbar ya query logging use karo.

**💬 Say this:**
> *"The N+1 problem happens when one query fetches a list, and then a separate query runs for each item to get its related object. So a hundred records become a hundred and one queries. I fix it with `select_related` or `prefetch_related`, and I usually detect it using Django Debug Toolbar or by logging the queries."*

---

### Migrations
**Samajh:** `makemigrations` model ke changes dekh ke ek migration file banata hai; `migrate` us file ko database pe apply karta hai. `showmigrations` se status dikhta hai, `sqlmigrate` se woh SQL dikhta hai jo chalega.

**💬 Say this:**
> *"`makemigrations` detects the changes in my models and creates a migration file, and `migrate` applies those changes to the database. I can also use `showmigrations` to check what has been applied, and `sqlmigrate` to see the actual SQL that will run."*

---

### Middleware ⭐
**Samajh:** Middleware request aur response ke beech ka **hook** hai — har request pe chalta hai. `settings.py` ki `MIDDLEWARE` list me **order matter karta hai**: request upar se neeche jaati hai, aur response neeche se upar wapas aata hai. Common examples: SecurityMiddleware, SessionMiddleware, AuthenticationMiddleware, CSRF.

**💬 Say this:**
> *"Middleware is a hook that sits between the request and the response, and it runs for every request. The order in the middleware list matters — the request passes through them from top to bottom, and the response comes back from bottom to top. Common ones are the authentication, session, and CSRF middleware."*

---

### Signals
**Samajh:** Signals decoupled notifications hain — jab kuch hota hai to koi aur code automatically chal jaata hai. Common: `pre_save`, `post_save`, `pre_delete`, `post_delete`, `m2m_changed`. **Par overuse mat karo** — signals se flow chhup jaata hai aur debugging mushkil ho jaati hai; aksar explicit service function better hota hai.

**💬 Say this:**
> *"Signals let one part of the application get notified when something happens elsewhere, like `post_save` after a model is saved. They are useful for decoupling, but I try not to overuse them, because they make the flow harder to follow and debug. Often an explicit service function is clearer."*

---

### CBV vs FBV
**Samajh:** **FBV** (function-based view) simple aur explicit hai — chhote, custom logic wale views ke liye achha. **CBV** (class-based view) inheritance aur mixins se reusable hai — standard CRUD ke liye `ListView`, `DetailView`, `CreateView` ready-made mil jaate hain, kam code likhna padta hai.

**💬 Say this:**
> *"Function-based views are simple and explicit, so I prefer them for small views with custom logic. Class-based views give reusability through inheritance and mixins, and Django provides ready-made ones like ListView and CreateView, which reduce boilerplate for standard CRUD operations."*

---

### Model relationships & `on_delete`
**Samajh:** `ForeignKey` = many-to-one, `OneToOneField` = one-to-one, `ManyToManyField` = many-to-many. `on_delete` batata hai ki **parent delete hone pe child ka kya karna hai**: `CASCADE` (child bhi delete), `PROTECT` (delete rokо, error do), `SET_NULL` (null kar do, `null=True` chahiye), `SET_DEFAULT`.

**💬 Say this:**
> *"`on_delete` defines what happens to the related rows when the parent object is deleted. `CASCADE` deletes the children as well, `PROTECT` prevents the deletion and raises an error, and `SET_NULL` sets the field to null, which requires the field to be nullable."*

---

### `null=True` vs `blank=True`
**Samajh:** `null` **database level** pe hai — column me NULL store ho sakta hai. `blank` **validation/form level** pe hai — form me field khaali chhod sakte ho. `CharField`/`TextField` me `null=True` avoid karo, kyunki phir "khaali" ki do states ban jaati hain (empty string aur NULL) — sirf `blank=True` use karo.

**💬 Say this:**
> *"`null` is database-level — it allows a NULL value in the column. `blank` is validation-level — it allows the field to be empty in forms. For text fields I avoid `null=True`, because then there would be two ways to represent empty, an empty string and NULL. So for text fields I only use `blank=True`."*

---

### QuerySet methods (jaan lo)
- `filter()` / `exclude()` / `get()` / `all()`
- **`annotate` vs `aggregate`** — `annotate` **har row** pe value jodta hai; `aggregate` poore queryset ka **ek** result deta hai
- **`Q` objects** — complex OR/AND conditions ke liye: `Q(a=1) | Q(b=2)`
- **`F` expressions** — DB level pe operation, race-free: `F('stock') - 1`
- `values()` / `values_list()` — dict / tuple me data
- `only()` / `defer()` — kaunse columns laane hain

**💬 Say this (F/Q):**
> *"`F` expressions let me reference a database column directly, so the update happens in the database itself. That avoids a race condition when two requests update the same row. `Q` objects let me build complex queries with OR and AND conditions."*

---

### Transactions
**Samajh:** `@transaction.atomic` ke andar ka poora block ek unit hai — sab kuch successful to commit, beech me koi exception aaya to **poora rollback**. Paise transfer, inventory update, order placement me zaroori.

**💬 Say this:**
> *"I use `transaction.atomic` to make a block of database operations atomic. If everything succeeds it commits, but if any exception occurs, the whole block is rolled back. This is important for operations like payments or inventory updates, where partial changes would corrupt the data."*

---

# PART D — DRF

### Serializer vs ModelSerializer
**Samajh:** `Serializer` me har field manually declare karna padta hai — full control. `ModelSerializer` model se fields **automatically** generate kar leta hai, aur `create()`/`update()` bhi de deta hai — Django ke `ModelForm` jaisa.

**💬 Say this:**
> *"A serializer converts complex data like querysets into JSON, and also validates incoming data. With a plain Serializer I define every field manually, whereas a ModelSerializer generates the fields automatically from the model and also provides the default create and update methods, so it needs much less code."*

---

### APIView vs ViewSet
**Samajh:** `APIView` me tu khud `get()`, `post()` methods likhta hai — zyada control. `ViewSet` CRUD actions (`list`, `create`, `retrieve`, `update`, `destroy`) ek jagah deta hai, aur `Router` se URLs **automatically** ban jaate hain.

**💬 Say this:**
> *"With an APIView I write the HTTP methods like get and post myself, which gives me more control. A ViewSet groups all the CRUD actions together, and when I register it with a router, the URLs are generated automatically. So I use ViewSets for standard CRUD and APIView when the logic is custom."*

---

### Authentication vs Permission ⭐
**Samajh:** **Authentication** = tu **kaun** hai (TokenAuthentication, JWT, SessionAuthentication). **Permission** = tu **kya kar sakta hai** (`IsAuthenticated`, `IsAdminUser`, custom permission class). Pehle authentication chalta hai, phir permission check hota hai.

**💬 Say this:**
> *"Authentication identifies who the user is — for example using a token or JWT. Permission decides what that user is allowed to do, using classes like `IsAuthenticated` or a custom permission. Authentication runs first, and then the permission check."*

---

### Validation
**Samajh:** `validate_<fieldname>()` — single field ke liye. `validate()` — poore object ke liye (jab do fields ka aapas me relation check karna ho). Error `serializers.ValidationError` raise karke dete hain.

---

# PART E — SQL (quick)

### Joins
**Samajh:** `INNER JOIN` — dono tables me match hone wali rows. `LEFT JOIN` — left table ki saari rows + right ka match (na mile to NULL). `RIGHT JOIN` — ulta. `FULL OUTER JOIN` — dono ka sab.

**💬 Say this:**
> *"An inner join returns only the rows that match in both tables. A left join returns all rows from the left table, and the matching rows from the right table, with NULLs where there is no match."*

### `WHERE` vs `HAVING` ⭐
**Samajh:** `WHERE` grouping se **pehle** individual rows filter karta hai; `HAVING` `GROUP BY` ke **baad** groups filter karta hai (aggregate pe condition).

**💬 Say this:**
> *"`WHERE` filters individual rows before grouping, while `HAVING` filters the groups after `GROUP BY`. So if I want to filter on an aggregate like count or sum, I have to use `HAVING`."*

### Index
**Samajh:** Index se read fast hota hai, par write thoda slow (kyunki index bhi update hota hai) aur extra storage lagti hai. Default B-Tree hota hai.

**💬 Say this:**
> *"An index speeds up reads by avoiding a full table scan, but it makes writes slightly slower because the index also has to be updated, and it uses extra storage. So I add indexes on columns that are frequently used in `WHERE` clauses or joins."*

### Baaki
`DELETE` (row-by-row, rollback ho sakta) vs `TRUNCATE` (fast, sab rows) vs `DROP` (table hi gaya) · Normalization 1NF/2NF/3NF · **ACID** (Atomicity, Consistency, Isolation, Durability)

Practice: [08_sql_interview_questions.md](08_sql_interview_questions.md)

---

# PART F — Project Story ⭐ *(Day 5 pe rehearse)*

**Risk:** Tera day job PHP/Laravel/Odoo hai. *"What is your Django production experience?"* pe atakna nahi hai.

**Samajh:** Jhooth mat bolna. Sach yeh hai ki **Odoo = real production Python** — wahan tune ORM models, business logic, integrations likhe hain. Odoo ka ORM concept-wise Django ke bahut kareeb hai (models, fields, relations, migrations). Yeh honest answer **weak nahi, strong** hai.

**💬 Say this:**
> *"My main production experience in Python has been with Odoo, where I built custom modules — writing ORM models, business logic, and third-party integrations. Odoo's ORM is conceptually quite close to Django's, with models, fields, and relations. Alongside that, I have worked deeply with Django and DRF on my own projects, where I implemented REST APIs, JWT authentication, and query optimisation like fixing N+1 problems."*

**Ek "problem I solved" story taiyaar rakho — STAR format:**
> *"In one of our modules, a listing page was very slow. When I checked the queries, I found we were hitting the database once for every row — an N+1 problem. I rewrote it to fetch the related data in a single query, and the response time went down from around two seconds to under three hundred milliseconds."*

**Rules:**
1. Numbers do — *"2 seconds to 300 milliseconds"* zyada strong hai *"it became faster"* se.
2. **5 baar bolke practice karo**, likhke nahi. ([English track](../../../english_speaking/README.md))
3. Ek honest gap accept karna theek hai: *"I haven't used that in production, but I understand the concept and have used something similar."*

---

# PART G — Managerial + HR Round 🔴 *(log ise underestimate karte hain)*

> **Research finding:** Infosys me experienced candidates ke liye ek alag **Managerial Round** hota hai — case studies, real-world situations, decision-making, team fit. Aur uske baad **HR round**. Yahan technical knowledge nahi, **communication aur attitude** dekha jaata hai — yani exactly tera focus area.
>
> **Rule:** Har answer **positive** rakho. Purane employer/colleague ki burai kabhi mat karo — yeh sabse bada red flag hai.

### 1. "Why are you looking for a job change?" ⭐⭐ *(guaranteed)*
**Samajh:** Yeh **trap question** hai. Kabhi mat bolna "salary kam hai", "manager achha nahi", "kaam boring hai". Hamesha **aage ki taraf** frame karo — kya paana chahte ho, na ki kya se bhaag rahe ho. Tera case genuine aur strong hai: tu Python me shift karna chahta hai.

**💬 Say this:**
> *"In my current role I've had good exposure to backend development and I've worked a lot with Python through Odoo. Over time I found that backend engineering with Python and Django is where my real interest is, and I've been building my depth there. I'm looking for a role where that is the core of my work, and where I can grow on larger scale systems — which is why this opportunity interested me."*

---

### 2. "Tell me about a challenge you faced" ⭐ *(STAR format)*
**Samajh:** **S**ituation → **T**ask → **A**ction → **R**esult. Result me **number** dena zaroori hai. Technical challenge chuno jo tune actually solve kiya ho.

**💬 Say this:**
> *"In one of our modules, a listing page had become very slow and users were complaining. When I looked into it, I found we were querying the database once for every row — a classic N+1 problem. I rewrote that part to fetch the related data in a single query and added an index on the column we were filtering on. The response time came down from around two seconds to under three hundred milliseconds, and the complaints stopped."*

---

### 3. "Tell me about a disagreement with a team member"
**Samajh:** Interviewer conflict **resolution** dekh raha hai, conflict nahi. Structure: disagreement tha → maine sunna aur data laana chuna → mil ke decide kiya → outcome achha raha. Kabhi mat bolna "main sahi tha, woh galat".

**💬 Say this:**
> *"We once disagreed on whether to fix an issue quickly or refactor the module properly, since we had a deadline. Instead of arguing, I asked for a short call and we listed the risks of both options. We agreed to do the quick fix to meet the deadline, but I raised a ticket and we refactored it in the next sprint. It worked out well because we made the decision together and nothing was left undocumented."*

---

### 4. "How do you handle tight deadlines / pressure?"
**💬 Say this:**
> *"I start by breaking the work down and identifying what is actually critical for the release versus what can go later. Then I communicate early — if I can see something will slip, I raise it as soon as possible rather than at the last moment. In my experience, early communication is what keeps a deadline manageable."*

---

### 5. "Why Infosys?"
**Samajh:** Homework dikhana hai. Scale, client diversity, learning/training culture, structured growth.

**💬 Say this:**
> *"Infosys works with a wide range of global clients, so there is exposure to different domains and large scale systems, which is something I haven't had in a smaller company. I also know Infosys invests heavily in structured learning, and since I'm actively building my depth in Python and Django, that environment suits how I like to grow."*

---

### 6. "Where do you see yourself in 5 years?"
**💬 Say this:**
> *"I'd like to grow into a senior backend engineer role, where I'm not just building features but also involved in designing systems and mentoring junior developers. Technically I want to go deeper into scalable backend architecture and cloud."*

---

### 7. "What are your strengths and weaknesses?"
**Samajh:** Weakness me real cheez bolo **+ uspe kya kar rahe ho**. "I'm a perfectionist" fake lagta hai. Tera honest weakness — communication/English — tu already improve kar raha hai, yeh strong answer hai.

**💬 Say this (strength):**
> *"My strength is that I'm consistent and self-driven with learning. Outside of work I've built a structured study track for backend and AI engineering, and I keep it up daily."*

**💬 Say this (weakness):**
> *"Earlier I used to hesitate while explaining my work in English, especially in meetings. I've been actively working on it — practising speaking daily and taking more chances to present my work — and I'm noticeably more comfortable now than I was six months ago."*

---

### 8. "Are you willing to relocate?" / "Notice period?" / "Salary expectations?"
- **Relocate:** *"Yes, I'm open to relocating for the right opportunity."* (agar sach ho tabhi)
- **Notice period:** apna actual number sach-sach bolo
- **Salary:** *"I'm currently at [X]. Based on my experience and the market, I'm looking for something in the range of [Y]. But I'm flexible if the role and growth are a good fit."*
  > 💡 Number pehle se decide karke jao — interview me calculate mat karo. Range do, single number nahi.

---

### 9. "Do you have any questions for us?" ⭐ *(hamesha HAAN bolo)*
**Samajh:** "No" bolna disinterest dikhata hai. 2–3 questions taiyaar rakho:

> *"What does the tech stack look like for this team day to day?"*
> *"How is the team structured, and who would I be working with most closely?"*
> *"What would success in this role look like in the first six months?"*

---

## 🗣️ Managerial round ke liye 3 niyam
1. **Dheere bolo.** Tez bolne se accent aur galtiyan dono badhte hain. Pause lena professional lagta hai.
2. **Har answer 30–60 second.** Bahut chhota = disinterest; bahut lamba = rambling.
3. **STAR yaad rakho** — situation, task, action, result. Result me hamesha ek number.

---

## ✅ Saturday subah — sirf yeh (naya kuch mat padhna)

1. **Part 0** ke saare 💬 answers — interpreted vs compiled, why Python, mutable vs immutable, class/object
2. **Project story** (Part F) — poora bolke, ek baar
3. **"Why job change"** (Part G #1) — bolke, ek baar
4. `select_related` vs `prefetch_related` + N+1
5. MVT flow
6. Decorator + generator
7. Interview English phrases (upar wali table)

> **Priority note:** Research ke hisaab se Infosys ke technical rounds *medium-to-easy* hote hain aur **project pe sabse zyada time** jaata hai. Isliye Part 0, F aur G (basics + story + managerial) ko Part A/B ke advanced gotchas se **zyada** weight do. GIL/MRO/`__slots__` bonus hain, must nahi.

**Confidence > cramming. Dheere bolo, saaf bolo. All the best 🚀**
