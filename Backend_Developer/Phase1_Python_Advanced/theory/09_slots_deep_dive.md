# `__slots__` — Deep Dive

> **Interview angle:** "Aapne kabhi `__slots__` production mein use kiya? Kab use karoge?"

---

## 1. Problem Statement — Default Python class ka overhead

Har Python instance ke saath ek **`__dict__`** attached hota hai — yeh dictionary attributes store karti hai. Dictionary flexible hai but **memory-heavy** hai.

```python
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

p = Point(1, 2)
print(p.__dict__)   # {'x': 1, 'y': 2}
p.new_attr = 99     # ✅ dynamically add — flexibility
```

**Memory cost:**
- Empty `dict` = ~232 bytes
- Plus per-attribute hash table entry
- 1 million Point instances = ~280 MB just for `__dict__`

---

## 2. Solution — `__slots__`

`__slots__` Python ko bolta hai: "Ye class sirf inhi attributes ko allow karegi — `__dict__` mat banao."

```python
class Point:
    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x = x
        self.y = y

p = Point(1, 2)
# p.__dict__   ❌ AttributeError — no dict!
p.x = 5        # ✅ allowed (in slots)
# p.new_attr = 99  ❌ AttributeError — not in slots
```

**Memory savings:** ~40-50% reduction per instance.

---

## 3. How `__slots__` works internally

Python descriptor protocol use karta hai:
- Class definition time pe har slot ke liye ek **member_descriptor** banta hai
- Instance memory mein attributes ek **fixed-size C array** mein store hote hain (not hash table)
- Lookup O(1) but **constant-time hash overhead nahi** (faster than dict)

```python
class Foo:
    __slots__ = ("a", "b")

print(type(Foo.a))   # <class 'member_descriptor'>
print(Foo.__slots__) # ('a', 'b')
```

---

## 4. Benchmarks (Real Numbers)

```python
import sys

class Normal:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class Slotted:
    __slots__ = ("x", "y")
    def __init__(self, x, y):
        self.x = x
        self.y = y

n = Normal(1, 2)
s = Slotted(1, 2)

# sys.getsizeof gives only object header
# Full size = object + __dict__ + keys table
# Normal: ~56 + 232 (dict) = ~288 bytes
# Slotted: ~48 bytes  (5-6x smaller)
```

**Attribute access speed:**
- Normal class: ~20-30 ns
- Slotted: ~15-20 ns (slightly faster, less indirection)

---

## 5. Inheritance Gotchas

### Gotcha 1: Parent without slots = child loses benefit

```python
class A:                  # no __slots__ — has __dict__
    pass

class B(A):
    __slots__ = ("x",)    # useless! B still gets __dict__ from A

b = B()
b.anything = 1            # works — A's __dict__ inherited
```

**Rule:** Sare ancestors mein `__slots__` chahiye to truly skip `__dict__`.

### Gotcha 2: Multiple inheritance breaks

```python
class A:
    __slots__ = ("x",)
class B:
    __slots__ = ("y",)
class C(A, B):
    __slots__ = ()
# ❌ TypeError: multiple bases have instance lay-out conflict
```

Reason: Memory layout ambiguous. Single inheritance only.

### Gotcha 3: Empty slots in subclass = need it

```python
class Parent:
    __slots__ = ("x",)

class Child(Parent):
    pass    # ❌ Child instances will HAVE __dict__ — slots lost

class Child(Parent):
    __slots__ = ()    # ✅ Explicit empty slots — preserves savings
```

---

## 6. `@dataclass(slots=True)` — Python 3.10+

Modern way — no manual `__slots__`:

```python
from dataclasses import dataclass

@dataclass(slots=True)
class Point:
    x: int
    y: int

# Automatically generates __slots__ = ('x', 'y')
# Plus __init__, __repr__, __eq__
```

**This is the recommended approach for new code.**

---

## 7. When to use `__slots__`

✅ **USE when:**
- Creating millions of instances (think simulation, ORM rows, graph nodes)
- Class is a simple data container (not adding methods dynamically)
- Memory is a bottleneck (profiled with `memory_profiler`)
- Hot path attribute access

❌ **DON'T use when:**
- Class is dynamic (plugins, ORM with dynamic fields)
- Multiple inheritance needed
- Mixing with classes you don't control (mixins, frameworks)
- Premature optimization — profile first

---

## 8. Real Production Use Cases

### a) ORM-like row objects (SQLAlchemy 2.0 uses slots internally)
```python
@dataclass(slots=True)
class UserRow:
    id: int
    email: str
    created_at: float
```

### b) Game/simulation entities
```python
class Particle:
    __slots__ = ("x", "y", "vx", "vy", "mass")
```

### c) Pydantic v2 `model_config = ConfigDict(slots=True)`
Pydantic supports slots-mode for ~30% memory reduction.

### d) Graph nodes (millions of edges)
```python
class GraphNode:
    __slots__ = ("id", "edges", "weight")
```

---

## 9. Common Pitfalls

### Pitfall 1: Picking + slots
```python
import pickle
class A:
    __slots__ = ("x",)

a = A()
a.x = 1
pickle.dumps(a)   # ✅ works in modern Python
```

### Pitfall 2: Default values
```python
class A:
    __slots__ = ("x",)
    x = 10        # ❌ ValueError! Can't have class default for slot

# Workaround:
class A:
    __slots__ = ("x",)
    def __init__(self):
        self.x = 10
```

### Pitfall 3: Weakref support
```python
class A:
    __slots__ = ("x",)

import weakref
ref = weakref.ref(A())   # ❌ TypeError

# Fix: explicitly include __weakref__
class A:
    __slots__ = ("x", "__weakref__")
```

---

## 10. Interview Questions

**Q1: `__slots__` se kya benefit milta hai?**
- Memory reduction (40-50%)
- Slightly faster attribute access
- Implicit "schema" — no typo'd attribute names

**Q2: Disadvantage?**
- No dynamic attribute addition
- Multiple inheritance issues
- Inheritance se savings lose ho jaati hai if parent has no slots
- Needs `__weakref__` slot for weak references

**Q3: dict vs slots — kaunsa fast hai?**
Slots ~5-10% faster for attribute access (no hash). Dict more flexible. For 1M+ objects, slots win on memory.

**Q4: Pydantic v2 mein slots use hota?**
Haan, opt-in via `model_config = ConfigDict(slots=True)`. Default off because of backward compatibility.

**Q5: dataclass slots vs manual?**
Same performance, less typing, plus `__init__`/`__repr__` auto-generated. Use dataclass slots in new code.

---

## 11. Key Takeaways

1. `__slots__` = memory optimization for **data-heavy classes**
2. Use `@dataclass(slots=True)` in Python 3.10+
3. Profile first — don't apply blindly
4. Watch out for inheritance + multiple inheritance issues
5. Excellent for ORM rows, simulation entities, graph nodes
6. Add `__weakref__` slot if you need weak references

---

## Related
- [[03_memory_gil]] — memory model + GC
- [[10_weakref_deep_dive]] — weakref needs __weakref__ slot
- [[06_metaclasses_descriptors]] — slots are descriptors under hood
