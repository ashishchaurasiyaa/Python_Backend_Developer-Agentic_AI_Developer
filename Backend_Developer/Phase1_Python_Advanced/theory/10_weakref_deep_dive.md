# `weakref` — Deep Dive

> **Interview angle:** "Memory leak debug kaise karoge jab cache + observer pattern ho?"

---

## 1. Problem — Strong References create cycles & leaks

Python me by default, har reference **strong** hoti hai — jab tak ek bhi reference hai, object alive rehta hai.

```python
cache = {}

class User:
    def __init__(self, name):
        self.name = name

u = User("Ashish")
cache["ashish"] = u    # strong ref
del u                  # User still alive in cache!
# u garbage collect nahi hoga jab tak cache se manually nikalo
```

**Real production problem:**
- Cache grows unbounded → OOM crash
- Observer pattern → observers never released → memory bloat
- Circular references (parent ↔ child) → leak (until gc runs)

---

## 2. Solution — `weakref` module

Weak reference object ko **alive nahi rakhta**. Jab last strong ref gayi, object gc ho jaata aur weakref `None` return karne lagta.

```python
import weakref

class User:
    def __init__(self, name):
        self.name = name

u = User("Ashish")
ref = weakref.ref(u)     # weak ref
print(ref())             # <User object>  — call to access

del u                    # last strong ref gone
import gc; gc.collect()
print(ref())             # None — object collected
```

---

## 3. Caveats — Not all objects support weakref

```python
weakref.ref([1,2,3])         # ❌ TypeError — list doesn't support
weakref.ref({"a": 1})        # ❌ TypeError — dict either
weakref.ref(42)              # ❌ TypeError — int either
```

**Only these support weakref:**
- User-defined classes (default)
- Most C extensions deliberately add it
- NOT: list, dict, tuple, int, str (memory-optimized stdlib types)

**Workaround — wrap in custom class:**
```python
class WeakableList(list): pass
weakref.ref(WeakableList([1,2,3]))   # ✅
```

**With `__slots__`:** Add `__weakref__` explicitly.
```python
class A:
    __slots__ = ("x", "__weakref__")
```

---

## 4. `weakref` API — The Big 4

### a) `weakref.ref(obj, callback=None)`
Basic weak reference. Call it (like a function) to dereference.

```python
ref = weakref.ref(obj, lambda r: print("obj died!"))
obj_again = ref()    # None or original
```

### b) `weakref.proxy(obj)`
Acts like the object directly — no need to call.

```python
proxy = weakref.proxy(user)
print(proxy.name)        # not proxy().name
# When original dies, accessing proxy raises ReferenceError
```

### c) `weakref.WeakValueDictionary`
Dict where **values** are weak. Auto-evict when value dies.

```python
cache = weakref.WeakValueDictionary()
u = User("Ashish")
cache["ashish"] = u
del u
# cache["ashish"] gone automatically
```

### d) `weakref.WeakKeyDictionary`
Dict where **keys** are weak. Use case: associate metadata with objects without keeping them alive.

```python
metadata = weakref.WeakKeyDictionary()
metadata[some_obj] = "extra info"
# when some_obj dies, entry removed
```

### e) `weakref.WeakSet`
Set of weak refs — auto-evict.

### f) `weakref.finalize(obj, func, *args)`
Modern alternative to `__del__`. Runs cleanup when object dies.

```python
class Resource:
    def __init__(self, name):
        self.name = name
        weakref.finalize(self, print, f"Cleaning up {name}")

r = Resource("DB conn")
del r
# Prints: "Cleaning up DB conn"
```

**Why `finalize` > `__del__`:**
- No reference cycle issues (`__del__` ko gc cycle me skip kar deta tha pre-3.4)
- Cleaner — no class method
- Atomic — runs exactly once

---

## 5. Real Production Use Cases

### Use Case 1: Bounded Cache (no manual eviction needed)
```python
import weakref

class ImageCache:
    def __init__(self):
        self._cache = weakref.WeakValueDictionary()

    def get(self, key):
        return self._cache.get(key)

    def put(self, key, image):
        self._cache[key] = image
        # When image not referenced elsewhere, auto-evicted
```

### Use Case 2: Observer Pattern (no leak)
```python
class Subject:
    def __init__(self):
        self._observers = weakref.WeakSet()

    def subscribe(self, obs):
        self._observers.add(obs)

    def notify(self):
        for obs in self._observers:
            obs.update()
# When observer dies, removed automatically — no leak
```

### Use Case 3: Circular Reference Resolution
```python
class Parent:
    def __init__(self):
        self.children = []

class Child:
    def __init__(self, parent):
        self.parent = weakref.ref(parent)   # weak! No cycle.

p = Parent()
c = Child(p)
p.children.append(c)
# No cycle — clean GC when p goes out of scope
```

### Use Case 4: Adding metadata to library objects
```python
metadata = weakref.WeakKeyDictionary()

def tag_object(obj, info):
    metadata[obj] = info

# Tag external lib objects without keeping them alive
import requests
session = requests.Session()
tag_object(session, {"created": "2025-05-24"})
```

### Use Case 5: Replacing `__del__` for resource cleanup
```python
import weakref

class FileHandle:
    def __init__(self, path):
        self.f = open(path)
        weakref.finalize(self, self.f.close)
```

---

## 6. Internals — How weakref works

CPython me har object ke header me ek field hota hai `tp_weaklistoffset`:
- 0 → object weakref support nahi karta (e.g., int, list)
- non-zero → offset where weakref linked list head stored

Jab object refcount 0 hota hai:
1. Destructor called
2. Weakref list traverse hoti hai
3. Har weakref ka callback fire hota hai (in reverse order)
4. Weakref objects `None` return karne lagte hain

**Performance:**
- Weakref creation: ~100-200 ns
- Deref (`ref()`): ~50 ns
- Negligible overhead for most workloads

---

## 7. Common Pitfalls

### Pitfall 1: Bound methods can't be weak-refed directly
```python
class A:
    def method(self): pass

a = A()
weakref.ref(a.method)   # ❌ TypeError
# Bound method is a temporary object — dies immediately

# Use WeakMethod
from weakref import WeakMethod
wm = WeakMethod(a.method)
wm()()   # call the method via weak ref
```

### Pitfall 2: Builtin containers don't support weakref
Use a custom subclass or wrap.

### Pitfall 3: lambdas in callbacks closing over the object
```python
# ❌ BAD — closure keeps obj alive!
ref = weakref.ref(obj, lambda r: print(obj))

# ✅ GOOD
ref = weakref.ref(obj, lambda r: print("died"))
```

### Pitfall 4: `WeakValueDictionary` mutation during iteration
```python
for k, v in cache.items():    # ❌ may explode if gc kicks in
    ...

# ✅ snapshot first
for k, v in list(cache.items()):
    ...
```

---

## 8. weakref vs `gc` module

| Feature | `weakref` | `gc` |
|---|---|---|
| Use case | Manual fine-grained refs | Cycle detection |
| Trigger | Refcount 0 | Generation-based scan |
| Overhead | Minimal | Larger but rare |
| Use together | Both for tricky cases | ✓ |

---

## 9. Interview Questions

**Q1: `weakref` kab use karte ho?**
- Caches (auto-evict)
- Observer pattern
- Breaking circular references
- Adding metadata to foreign objects
- Resource finalization (replace `__del__`)

**Q2: `weakref` vs strong ref difference?**
Strong ref refcount badhata hai. Weak nahi. Last strong ref gone = object dies, weakref returns None.

**Q3: list/dict pe weakref kyu nahi?**
CPython optimization — common containers ka memory layout fixed rakha. Custom subclass se possible.

**Q4: `__del__` ki jagah `weakref.finalize` kyu prefer karein?**
- No cycle issues
- Guaranteed to run
- Cleaner — outside class
- Multiple finalizers allowed per object

**Q5: `WeakValueDictionary` race condition?**
GC mid-iteration entries delete kar sakta — `list(cache.items())` se snapshot lo.

**Q6: Production memory leak — kaise debug?**
1. `tracemalloc` snapshot
2. `objgraph.show_growth()` — kaunsa class grow ho raha
3. `objgraph.show_backrefs()` — kaun reference hold kar raha
4. Suspected leak source pe `weakref` introduce karo

---

## 10. Key Takeaways

1. `weakref` = ref jo object ko alive nahi rakhti
2. Use `WeakValueDictionary` for auto-evicting caches
3. Use `WeakSet` for observer patterns
4. Use `weakref.finalize` instead of `__del__`
5. Builtin types (list/dict/int) don't support — subclass karna padta
6. Add `__weakref__` slot if using `__slots__`

---

## Related
- [[09_slots_deep_dive]] — needs `__weakref__` slot
- [[03_memory_gil]] — refcount + GC
- [[12_deadlock_debugging]] — circular refs can cause issues
