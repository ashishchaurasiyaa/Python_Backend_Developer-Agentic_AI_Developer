# Prototype Pattern

> **Category:** Creational Design Pattern
> **Intent:** Create new objects by **copying** an existing object (prototype), instead of constructing from scratch.

---

## 1. Problem Statement

Sometimes object creation is:
- **Expensive** — DB query, file load, network call
- **Complex** — many configuration steps
- **Sensitive** — copying needed without exposing internals

Building a fresh object every time wastes resources. **Prototype pattern** says: "Keep one fully-built object as a template, clone it when you need more."

---

## 2. Real-World Analogies

- **Document templates** in Word — open a template, edit a copy
- **Game enemies** — create one "boss" prototype, spawn clones
- **Database snapshots** — clone state for testing
- **Browser tab duplication** — clone current tab with all state

---

## 3. Structure (UML)

```
┌─────────────────┐
│   Prototype     │  <interface>
│─────────────────│
│ + clone()       │
└─────────────────┘
         ▲
         │
   ┌─────┴───────────┐
   │                 │
┌──────────┐  ┌──────────┐
│ConcreteA │  │ConcreteB │
│clone()   │  │clone()   │
└──────────┘  └──────────┘
```

---

## 4. Python Implementation Approaches

### Approach 1: `copy.copy()` (shallow) / `copy.deepcopy()` (deep)
```python
import copy

class Document:
    def __init__(self, content, metadata):
        self.content = content
        self.metadata = metadata

prototype = Document("Hello", {"author": "Ashish"})
clone = copy.deepcopy(prototype)
clone.content = "World"   # original unchanged
```

### Approach 2: Custom `clone()` method
```python
class Document:
    def clone(self):
        new = Document(self.content, self.metadata.copy())
        return new
```

### Approach 3: `__copy__` / `__deepcopy__` magic methods
```python
class Document:
    def __deepcopy__(self, memo):
        # Custom deep copy logic
        new = Document(self.content, copy.deepcopy(self.metadata, memo))
        new._cache = None   # exclude cache from copy
        return new
```

---

## 5. Shallow vs Deep Copy

| Aspect | Shallow Copy | Deep Copy |
|---|---|---|
| Top-level object | New | New |
| Nested objects | **Shared** (same reference) | New (recursive) |
| Speed | Fast | Slower |
| Use case | Immutable nested | Mutable nested |
| Python | `copy.copy()` | `copy.deepcopy()` |

**Example:**
```python
import copy
original = {"users": [1, 2, 3]}
shallow = copy.copy(original)
deep    = copy.deepcopy(original)

original["users"].append(4)
print(shallow["users"])  # [1, 2, 3, 4]  — shared!
print(deep["users"])     # [1, 2, 3]      — independent
```

---

## 6. Use Cases

### ✅ Use when:
- Object creation is expensive (DB, file load, network)
- Many similar objects with slight variations
- Need to avoid coupling client to constructor logic
- Configuration object with many defaults — clone + tweak

### ❌ Don't use when:
- Objects are simple/cheap to create
- Circular references (`deepcopy` will handle but slow)
- Objects shouldn't be cloned (singletons, locks, file handles)

---

## 7. Real Production Examples

### Example 1: Configuration cloning
```python
default_config = AppConfig(
    timeout=30,
    retries=3,
    debug=False,
)
dev_config = copy.deepcopy(default_config)
dev_config.debug = True
```

### Example 2: ORM record duplication
```python
# Django
new_post = copy.copy(original_post)
new_post.pk = None       # so save() creates new row
new_post.save()
```

### Example 3: Game entity spawning
```python
class Enemy:
    def __init__(self, type, hp, dmg):
        self.type, self.hp, self.dmg = type, hp, dmg
    def clone(self):
        return Enemy(self.type, self.hp, self.dmg)

goblin_template = Enemy("goblin", 50, 10)
goblins = [goblin_template.clone() for _ in range(100)]
```

### Example 4: Test fixtures
```python
def fixture_user():
    return User(name="Test", email="t@t.com", role="user")

# In each test:
user = copy.deepcopy(fixture_user())
user.role = "admin"
```

### Example 5: Prototype registry (factory + prototype combo)
```python
class PrototypeRegistry:
    def __init__(self):
        self._prototypes = {}
    def register(self, name, prototype):
        self._prototypes[name] = prototype
    def create(self, name, **overrides):
        clone = copy.deepcopy(self._prototypes[name])
        for k, v in overrides.items():
            setattr(clone, k, v)
        return clone
```

---

## 8. Pitfalls

### Pitfall 1: Forgetting deep copy on mutable nested data
```python
class Cart:
    def __init__(self):
        self.items = []

c1 = Cart()
c2 = copy.copy(c1)   # shallow — items shared!
c2.items.append("X") # affects c1 too!
```

### Pitfall 2: Cloning objects with external resources
```python
class Connection:
    def __init__(self):
        self.socket = open_socket()   # ❌ clone will share socket!
```
Fix: Override `__deepcopy__` to recreate resource.

### Pitfall 3: `pk` not reset in ORM
```python
new_post = copy.copy(post)
new_post.save()        # UPDATEs original instead of INSERT!
# Fix: new_post.pk = None
```

### Pitfall 4: Circular references slow `deepcopy`
Use `memo` parameter to avoid infinite loops (Python handles by default but slow on big graphs).

---

## 9. Interview Questions

**Q1: Prototype vs Factory?**
- Factory: creates from scratch using params
- Prototype: copies existing instance (faster, preserves state)

**Q2: Shallow vs deep copy?**
Shallow shares nested refs; deep recurses. Choose based on mutability of contents.

**Q3: When NOT to use Prototype?**
- Cheap creation (no benefit)
- Resources can't be cloned (file handles, sockets)
- Immutable objects (just reference, no clone needed)

**Q4: Real production example?**
- Cloning request context for retry
- Test fixture duplication
- Config templates → environment-specific copies
- ORM record duplication

**Q5: Python ke `copy` module ka difference vs custom clone?**
`copy.deepcopy` is generic recursive. Custom clone is faster + can selectively skip fields (caches, sockets).

**Q6: Singleton + Prototype conflict?**
Singletons shouldn't be cloned — block via `__copy__ = __deepcopy__ = lambda self, _=None: self`.

---

## 10. Key Takeaways

1. **Prototype = copy existing**, not construct new
2. Use **`copy.deepcopy`** for mutable nested data
3. Override `__deepcopy__` to **exclude** caches/resources
4. Combine with **registry** for prototype catalog pattern
5. **Reset identity fields** (pk, id) in cloned ORM objects
6. Don't clone **shared resources** (sockets, file handles)

---

## Related
- [[02_Factory_Pattern]] — alternate creation strategy
- [[04_Builder_Pattern]] — step-by-step construction
- [[01_Singleton_Pattern]] — opposite philosophy
