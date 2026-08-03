# Python Idioms vs GoF — Where the Language Eats the Pattern

> GoF patterns were written for C++/Java in 1994. Python has first-class functions, decorators, dunders, and modules — several patterns collapse into **one line**. Writing the Java version in Python is the #1 way to look junior in a senior interview.

## 1. The collapse table

| GoF Pattern | Java needs | Python idiom that replaces it |
|---|---|---|
| **Strategy** | Interface + N classes + setter | A function passed as an argument; `dict[str, Callable]` |
| **Command** | Interface + class per command | A closure or `functools.partial` |
| **Singleton** | Private ctor + static instance + locking | A **module** (imported once, cached in `sys.modules`) |
| **Factory Method** | Abstract creator hierarchy | A function returning objects; `dict` registry |
| **Template Method** | Abstract class + hooks | A function taking callbacks; or a decorator |
| **Decorator (structural)** | Wrapper class hierarchy | `@decorator` syntax + `functools.wraps` |
| **Iterator** | Interface with `hasNext()`/`next()` | Generators (`yield`) — the pattern *is* the language |
| **Adapter** | Wrapper class | Duck typing; often nothing is needed at all |
| **Observer** | Listener interfaces + registry | A list of callables; or `blinker`/Django signals |
| **Prototype** | `clone()` method | `copy.deepcopy()` |
| **Flyweight** | Object pool | `functools.lru_cache`; interned immutables |
| **Chain of Responsibility** | Handler classes with `next` | A list of functions in a loop; ASGI/WSGI middleware |

---

## 2. Side-by-side — Strategy

```python
# ❌ Java-in-Python — 20 lines to select a function
class DiscountStrategy(ABC):
    @abstractmethod
    def apply(self, amount: Decimal) -> Decimal: ...

class NoDiscount(DiscountStrategy):
    def apply(self, amount): return amount

class PercentDiscount(DiscountStrategy):
    def __init__(self, pct): self.pct = pct
    def apply(self, amount): return amount * (1 - self.pct)

class Checkout:
    def __init__(self, strategy: DiscountStrategy): self.strategy = strategy

# ✅ Pythonic — the "interface" is Callable[[Decimal], Decimal]
def percent(pct: Decimal) -> Callable[[Decimal], Decimal]:
    return lambda amount: amount * (1 - pct)

DISCOUNTS = {"none": lambda a: a, "diwali": percent(Decimal("0.2"))}
total = DISCOUNTS[code](amount)
```

**When classes still win:** the strategy has **state** (counters, connections), needs multiple related methods, or must be serializable/registered via DI. Then a `Protocol` + classes is right — that's not Java-ism, that's the pattern earning its cost.

---

## 3. Singleton — just use a module

```python
# ❌ The interview trap answer
class Config:
    _instance = None
    def __new__(cls):
        if cls._instance is None: cls._instance = super().__new__(cls)
        return cls._instance     # not even thread-safe

# ✅ Python: a module IS a singleton — imported once, cached in sys.modules
# config.py
settings = Settings()            # created once at import

# anywhere: from config import settings

# ✅ Or, when you need laziness + testability:
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()            # FastAPI's canonical pattern — overridable in tests
```

**Interview line:** *"Singleton in Python is usually a module-level object or an `lru_cache`d factory. I avoid the `__new__` version because it fights the language and makes tests hard — the FastAPI `Depends(get_settings)` form gives me the same single instance plus an override seam."*

---

## 4. Decorator — the language stole the name

GoF Decorator = wrap an object to add behavior. Python's `@decorator` = wrap a *function*. Both are the same idea at different granularity:

```python
# Behavior added without touching the wrapped callable
def retry(times: int):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **kw):
            for attempt in range(times):
                try: return fn(*a, **kw)
                except TransientError:
                    if attempt == times - 1: raise
                    time.sleep(2 ** attempt)
        return wrapper
    return deco

@retry(3)
def charge(order_id: str): ...
```

Object-level decoration (wrapping an *instance*) still needs the classical form — e.g. wrapping a `Storage` object with `CachedStorage`, `EncryptedStorage`. Function-level → use `@`.

---

## 5. Iterator & friends — generators everywhere

```python
# The GoF Iterator interface is literally the iterator protocol
def batched_rows(qs, size=1000):
    buf = []
    for row in qs.iterator():        # Django: server-side cursor, no memory blowup
        buf.append(row)
        if len(buf) == size:
            yield buf; buf = []
    if buf: yield buf
```

`yield` also gives you a **Template Method** (the generator defines skeleton, caller decides what to do per item) and lazy pipelines that in Java need a whole Streams API.

---

## 6. Dunder methods = pattern hooks

| Want | Dunder |
|---|---|
| Proxy / lazy loading | `__getattr__`, `__getattribute__` |
| Context (setup/teardown) | `__enter__`/`__exit__` — or `@contextmanager` |
| Callable strategy objects | `__call__` |
| Value-object equality | `__eq__`, `__hash__`, or `@dataclass(frozen=True)` |
| Collection façade | `__len__`, `__iter__`, `__getitem__` |

```python
# Proxy without a Proxy class hierarchy
class LazyClient:
    def __init__(self, factory): self._factory, self._obj = factory, None
    def __getattr__(self, name):            # called only for missing attrs
        if self._obj is None: self._obj = self._factory()
        return getattr(self._obj, name)
```

---

## 7. The rule

```
Ask in this order:
  1. Can a FUNCTION do it?              → do that
  2. Can a stdlib idiom do it?          → dict/closure/decorator/generator/dataclass
  3. Does it need STATE + multiple ops?  → now use the class-based pattern
  4. Does the team/codebase expect the classical form? → consistency wins
```

**Interview framing:** *"I know the GoF form, but in Python I reach for the idiom first — Strategy is usually a callable, Singleton is a module, Iterator is a generator. I go classical when the pattern needs state or a stable interface across many implementations."* That sentence signals you know both, and chose.

---

## 8. Self-check

1. Why is a module a better Singleton than `__new__` tricks in Python?
2. When does Strategy genuinely deserve classes instead of functions?
3. GoF Decorator vs Python `@decorator` — same or different? Where do they diverge?
4. Which dunder pair replaces the Proxy pattern for lazy loading?
5. Name a pattern Python does *not* trivialize, and why. (Hint: Visitor, Mediator, State-with-transitions.)

---

**Related:** [Behavioral](../Section_06_Behavioral/) · [Backend Mapping](../Section_08_Backend_Mapping/) · [Anti-Patterns](../Section_09_Anti_Patterns/)
