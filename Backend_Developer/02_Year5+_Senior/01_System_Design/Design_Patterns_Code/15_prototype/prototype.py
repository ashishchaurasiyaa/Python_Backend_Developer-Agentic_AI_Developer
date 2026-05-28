"""
============================================================
PROTOTYPE PATTERN — Practical Implementation
============================================================
Run:  python prototype.py
"""
import copy
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ============================================================
# 1. BASIC PROTOTYPE INTERFACE
# ============================================================
class Prototype(ABC):
    @abstractmethod
    def clone(self) -> "Prototype":
        ...


# ============================================================
# 2. CONCRETE CLASS — Document with custom clone
# ============================================================
class Document(Prototype):
    def __init__(self, title: str, content: str, tags: list[str]):
        self.title = title
        self.content = content
        self.tags = tags    # mutable!

    def clone(self) -> "Document":
        # Manual deep copy of mutable members
        return Document(self.title, self.content, self.tags.copy())

    def __repr__(self):
        return f"Document(title={self.title!r}, tags={self.tags})"


# ============================================================
# 3. USING copy.deepcopy
# ============================================================
@dataclass
class AppConfig:
    db_host: str
    db_port: int
    features: dict = field(default_factory=dict)
    plugins: list = field(default_factory=list)


def demo_basic_clone():
    print("=" * 60)
    print("DEMO 1: Basic clone (custom method)")
    print("=" * 60)
    doc = Document("Report", "Sales data...", ["finance", "Q4"])
    clone = doc.clone()
    clone.title = "Report Copy"
    clone.tags.append("copy")
    print(f"  Original: {doc}")
    print(f"  Clone   : {clone}")


def demo_deepcopy():
    print("\n" + "=" * 60)
    print("DEMO 2: copy.deepcopy with dataclass")
    print("=" * 60)

    default = AppConfig(
        db_host="localhost",
        db_port=5432,
        features={"cache": True, "metrics": True},
        plugins=["auth", "logging"],
    )

    dev = copy.deepcopy(default)
    dev.db_host = "dev.example.com"
    dev.features["debug"] = True
    dev.plugins.append("profiler")

    print(f"  Default: {default}")
    print(f"  Dev    : {dev}")
    print("  ✅ Default unchanged after dev modification")


# ============================================================
# 4. SHALLOW VS DEEP COPY
# ============================================================
def demo_shallow_vs_deep():
    print("\n" + "=" * 60)
    print("DEMO 3: Shallow vs Deep copy")
    print("=" * 60)

    original = {"users": [1, 2, 3], "name": "team"}

    shallow = copy.copy(original)
    deep = copy.deepcopy(original)

    original["users"].append(4)
    original["name"] = "team-alpha"

    print(f"  Original: {original}")
    print(f"  Shallow : {shallow}  ← users shared!")
    print(f"  Deep    : {deep}     ← independent")


# ============================================================
# 5. CUSTOM __deepcopy__ — exclude caches/resources
# ============================================================
class DBConnection:
    """Simulates non-cloneable resource."""
    def __init__(self, host):
        self.host = host
        print(f"    [DBConnection] Opening connection to {host}")
    def __deepcopy__(self, memo):
        # Reopen instead of cloning the socket
        return DBConnection(self.host)
    def __repr__(self):
        return f"DBConnection({self.host})"


class CachedService:
    def __init__(self, name):
        self.name = name
        self.connection = DBConnection("prod-db.example.com")
        self._cache = {"big": list(range(100000))}

    def __deepcopy__(self, memo):
        # Reset cache on clone, recreate connection via its own __deepcopy__
        new = CachedService.__new__(CachedService)
        new.name = self.name
        new.connection = copy.deepcopy(self.connection, memo)
        new._cache = {}    # don't clone heavy cache
        return new

    def __repr__(self):
        return f"CachedService({self.name}, conn={self.connection}, cache_size={len(self._cache)})"


def demo_custom_deepcopy():
    print("\n" + "=" * 60)
    print("DEMO 4: Custom __deepcopy__ — skip cache, recreate resource")
    print("=" * 60)
    original = CachedService("svc-1")
    print(f"  Original  : {original}")
    cloned = copy.deepcopy(original)
    print(f"  Cloned    : {cloned}")
    print("  ✅ Cache reset, connection reopened (not shared)")


# ============================================================
# 6. PROTOTYPE REGISTRY (Catalog Pattern)
# ============================================================
class PrototypeRegistry:
    """Registers prototypes by key; creates clones on demand with overrides."""
    def __init__(self):
        self._prototypes: dict[str, Any] = {}

    def register(self, key: str, prototype: Any):
        self._prototypes[key] = prototype

    def create(self, key: str, **overrides) -> Any:
        if key not in self._prototypes:
            raise KeyError(f"No prototype '{key}'")
        clone = copy.deepcopy(self._prototypes[key])
        for attr, value in overrides.items():
            setattr(clone, attr, value)
        return clone

    def list_keys(self) -> list[str]:
        return list(self._prototypes.keys())


@dataclass
class Enemy:
    type: str
    hp: int
    damage: int
    abilities: list[str] = field(default_factory=list)


def demo_prototype_registry():
    print("\n" + "=" * 60)
    print("DEMO 5: Prototype Registry")
    print("=" * 60)

    registry = PrototypeRegistry()
    registry.register("goblin", Enemy("Goblin", 50, 10, ["bite"]))
    registry.register("dragon", Enemy("Dragon", 500, 80, ["fire", "fly"]))
    registry.register("ogre", Enemy("Ogre", 200, 30, ["smash"]))

    print(f"  Available: {registry.list_keys()}")

    goblin1 = registry.create("goblin")
    goblin2 = registry.create("goblin", hp=80)        # boosted variant
    dragon = registry.create("dragon", abilities=["fire", "fly", "ice"])

    print(f"  Spawned: {goblin1}")
    print(f"  Spawned: {goblin2}")
    print(f"  Spawned: {dragon}")


# ============================================================
# 7. REAL-WORLD: ORM Record Duplication
# ============================================================
@dataclass
class BlogPost:
    pk: int | None
    title: str
    body: str
    tags: list[str]
    views: int = 0


def duplicate_post(post: BlogPost) -> BlogPost:
    """Clone and reset identity for ORM-like INSERT."""
    new = copy.deepcopy(post)
    new.pk = None              # ORM treats None pk as INSERT
    new.title = post.title + " (Copy)"
    new.views = 0              # reset stats
    return new


def demo_orm_clone():
    print("\n" + "=" * 60)
    print("DEMO 6: ORM-style record duplication")
    print("=" * 60)

    original = BlogPost(
        pk=42,
        title="My Original Post",
        body="Content...",
        tags=["python", "design"],
        views=1500,
    )
    copy_post = duplicate_post(original)
    print(f"  Original: {original}")
    print(f"  Copy    : {copy_post}")
    print("  ✅ pk reset to None, views reset, title marked")


# ============================================================
# 8. PREVENT CLONING (singleton style)
# ============================================================
class DatabasePool:
    """Singleton — must NOT be cloned."""
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __copy__(self):
        return self
    def __deepcopy__(self, memo):
        return self


def demo_block_cloning():
    print("\n" + "=" * 60)
    print("DEMO 7: Block cloning (singleton-like)")
    print("=" * 60)
    pool = DatabasePool()
    cloned = copy.deepcopy(pool)
    print(f"  pool is cloned? {pool is cloned}  (expected True — same instance)")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_basic_clone()
    demo_deepcopy()
    demo_shallow_vs_deep()
    demo_custom_deepcopy()
    demo_prototype_registry()
    demo_orm_clone()
    demo_block_cloning()

    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS")
    print("=" * 60)
    print("""
1. Use copy.deepcopy() for most cases
2. Override __deepcopy__ to skip caches / recreate resources
3. Registry pattern: catalog of prototypes + clone-with-overrides
4. Reset identity (pk, id) when cloning ORM records
5. Block cloning for singletons via __copy__ = lambda self: self
6. Prototype is cheaper than full reconstruction for expensive objects
""")
