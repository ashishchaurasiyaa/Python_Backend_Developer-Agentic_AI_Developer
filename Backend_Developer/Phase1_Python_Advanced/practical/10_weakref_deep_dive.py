"""
weakref — Practical Demos
=========================
Caches, observers, finalize, circular ref breaking, gotchas.
"""
import gc
import weakref
import time


# ============================================================
# DEMO 1: Basic weak reference
# ============================================================
class User:
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return f"User({self.name})"


def demo_basic():
    print("=" * 60)
    print("DEMO 1: Basic weakref.ref")
    print("=" * 60)
    u = User("Ashish")
    ref = weakref.ref(u)
    print(f"  ref()         = {ref()}")
    print(f"  ref is alive  = {ref() is not None}")

    del u
    gc.collect()
    print(f"  After del u   = {ref()}")
    print(f"  ref is alive  = {ref() is not None}")


# ============================================================
# DEMO 2: weakref callback when object dies
# ============================================================
def demo_callback():
    print("\n" + "=" * 60)
    print("DEMO 2: Weakref callback")
    print("=" * 60)

    def on_death(r):
        print(f"  💀 Object died! Weak ref now: {r()}")

    u = User("temp")
    ref = weakref.ref(u, on_death)
    print(f"  Before del: {ref()}")
    del u
    gc.collect()


# ============================================================
# DEMO 3: weakref.proxy — transparent access
# ============================================================
def demo_proxy():
    print("\n" + "=" * 60)
    print("DEMO 3: weakref.proxy")
    print("=" * 60)
    u = User("ProxyUser")
    p = weakref.proxy(u)
    print(f"  Access via proxy: {p.name}")    # no need to call p()

    del u
    gc.collect()
    try:
        print(p.name)
    except ReferenceError as e:
        print(f"  After del: ReferenceError -> {e}")


# ============================================================
# DEMO 4: WeakValueDictionary — auto-evicting cache
# ============================================================
def demo_weak_value_dict():
    print("\n" + "=" * 60)
    print("DEMO 4: WeakValueDictionary (auto-evict cache)")
    print("=" * 60)

    cache = weakref.WeakValueDictionary()

    u1 = User("u1")
    u2 = User("u2")
    cache["u1"] = u1
    cache["u2"] = u2
    print(f"  Cache size after add: {len(cache)}")

    del u1
    gc.collect()
    print(f"  Cache size after del u1: {len(cache)}")
    print(f"  Still has u2: {cache.get('u2')}")


# ============================================================
# DEMO 5: WeakSet — observer pattern without leak
# ============================================================
class Subject:
    def __init__(self):
        self._observers = weakref.WeakSet()

    def subscribe(self, obs):
        self._observers.add(obs)

    def notify(self):
        for obs in list(self._observers):
            obs.on_event()


class Observer:
    def __init__(self, name):
        self.name = name
    def on_event(self):
        print(f"    [{self.name}] received event")


def demo_weak_set_observer():
    print("\n" + "=" * 60)
    print("DEMO 5: WeakSet for Observer pattern")
    print("=" * 60)

    subj = Subject()
    o1 = Observer("Alice")
    o2 = Observer("Bob")
    subj.subscribe(o1)
    subj.subscribe(o2)

    print("  Notify (2 observers):")
    subj.notify()

    del o1
    gc.collect()
    print("  Notify after del o1 (auto-cleaned):")
    subj.notify()


# ============================================================
# DEMO 6: WeakKeyDictionary — metadata without keeping alive
# ============================================================
def demo_weak_key_dict():
    print("\n" + "=" * 60)
    print("DEMO 6: WeakKeyDictionary (metadata)")
    print("=" * 60)

    metadata = weakref.WeakKeyDictionary()
    u = User("withmeta")
    metadata[u] = {"created": time.time(), "tag": "premium"}
    print(f"  Metadata set: {metadata[u]}")

    del u
    gc.collect()
    print(f"  After del, metadata count: {len(metadata)}")


# ============================================================
# DEMO 7: weakref.finalize — modern __del__ replacement
# ============================================================
class DBConnection:
    def __init__(self, host):
        self.host = host
        print(f"  📡 Connected to {host}")
        weakref.finalize(self, self._cleanup, host)

    @staticmethod
    def _cleanup(host):
        print(f"  🔌 Disconnected from {host}")


def demo_finalize():
    print("\n" + "=" * 60)
    print("DEMO 7: weakref.finalize")
    print("=" * 60)
    conn = DBConnection("db.prod.com")
    del conn
    gc.collect()


# ============================================================
# DEMO 8: Circular reference resolution
# ============================================================
class Parent:
    def __init__(self):
        self.children = []
    def __repr__(self):
        return f"Parent(children={len(self.children)})"


class ChildStrong:
    def __init__(self, parent):
        self.parent = parent       # strong ref — creates cycle


class ChildWeak:
    def __init__(self, parent):
        self.parent_ref = weakref.ref(parent)   # weak

    @property
    def parent(self):
        return self.parent_ref()


def demo_circular():
    print("\n" + "=" * 60)
    print("DEMO 8: Breaking circular references")
    print("=" * 60)

    # Strong ref cycle
    p1 = Parent()
    c1 = ChildStrong(p1)
    p1.children.append(c1)

    initial = len(gc.get_objects())
    del p1, c1
    # without gc.collect(), refcount-based dealloc fails (cycle)
    collected = gc.collect()
    print(f"  Strong cycle — gc.collect() picked up: {collected} objects")

    # Weak ref — no cycle
    p2 = Parent()
    c2 = ChildWeak(p2)
    p2.children.append(c2)
    print(f"  Child can access parent: {c2.parent}")
    del p2
    gc.collect()
    print(f"  After del parent, child.parent = {c2.parent}")


# ============================================================
# DEMO 9: WeakMethod — for bound methods
# ============================================================
def demo_weak_method():
    print("\n" + "=" * 60)
    print("DEMO 9: WeakMethod for bound methods")
    print("=" * 60)

    class Handler:
        def handle(self, event):
            print(f"    Handling: {event}")

    h = Handler()

    # Bound method weakref directly = doesn't work
    try:
        ref = weakref.ref(h.handle)
        time.sleep(0.01)
        print(f"  Direct ref to bound method: {ref()}")
    except TypeError as e:
        print(f"  Direct weakref.ref(bound): {e}")

    # WeakMethod works
    wm = weakref.WeakMethod(h.handle)
    method = wm()
    if method:
        method("event1")
    print(f"  WeakMethod alive: {wm() is not None}")
    del h
    gc.collect()
    print(f"  After del handler: {wm()}")


# ============================================================
# DEMO 10: Builtin types don't support weakref
# ============================================================
def demo_builtin_limitation():
    print("\n" + "=" * 60)
    print("DEMO 10: Builtin types limitation")
    print("=" * 60)

    for obj in [[1, 2, 3], {"a": 1}, (1, 2), "string", 42]:
        try:
            weakref.ref(obj)
        except TypeError as e:
            print(f"  {type(obj).__name__:8s} -> ❌ {e}")

    # Workaround
    class MyList(list): pass
    ml = MyList([1, 2, 3])
    r = weakref.ref(ml)
    print(f"  Custom MyList(list) -> ✅ {r()}")


# ============================================================
# DEMO 11: Production cache pattern
# ============================================================
class ImageCache:
    def __init__(self):
        self._cache = weakref.WeakValueDictionary()
        self._hits = 0
        self._misses = 0

    def get(self, key):
        img = self._cache.get(key)
        if img is None:
            self._misses += 1
        else:
            self._hits += 1
        return img

    def put(self, key, image):
        self._cache[key] = image

    def stats(self):
        return f"hits={self._hits}, misses={self._misses}, size={len(self._cache)}"


class Image:
    def __init__(self, data):
        self.data = data


def demo_production_cache():
    print("\n" + "=" * 60)
    print("DEMO 11: Production-style auto-evicting cache")
    print("=" * 60)
    cache = ImageCache()

    # Strong ref outside cache → stays
    img1 = Image("photo1.jpg data")
    cache.put("photo1", img1)

    # No strong ref outside → eligible for collection
    cache.put("photo2", Image("photo2.jpg data"))

    gc.collect()
    print(f"  After GC: {cache.stats()}")
    print(f"  Get photo1: {cache.get('photo1')}")
    print(f"  Get photo2: {cache.get('photo2')} (evicted — no strong ref)")
    print(f"  Final stats: {cache.stats()}")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_basic()
    demo_callback()
    demo_proxy()
    demo_weak_value_dict()
    demo_weak_set_observer()
    demo_weak_key_dict()
    demo_finalize()
    demo_circular()
    demo_weak_method()
    demo_builtin_limitation()
    demo_production_cache()

    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS")
    print("=" * 60)
    print("1. weakref.ref + callback for death notifications")
    print("2. WeakValueDictionary for auto-evicting cache")
    print("3. WeakSet for leak-free observer pattern")
    print("4. weakref.finalize replaces __del__ (cleaner, safer)")
    print("5. WeakMethod for callback registration with bound methods")
    print("6. Subclass builtin types if you need weakref support")
