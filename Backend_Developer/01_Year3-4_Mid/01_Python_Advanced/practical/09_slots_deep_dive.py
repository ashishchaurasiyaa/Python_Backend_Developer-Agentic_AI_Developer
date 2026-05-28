"""
__slots__ — Practical Demos
============================
Memory, speed, inheritance gotchas, pickling, weakref.
"""
import sys
import time
import tracemalloc
import pickle
import weakref
from dataclasses import dataclass


# ============================================================
# DEMO 1: Memory comparison
# ============================================================
class NormalPoint:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class SlottedPoint:
    __slots__ = ("x", "y")
    def __init__(self, x, y):
        self.x = x
        self.y = y


@dataclass(slots=True)
class DataPoint:
    x: int
    y: int


def measure_memory(cls, n=100_000):
    tracemalloc.start()
    instances = [cls(i, i) for i in range(n)]
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    # cleanup ref
    del instances
    return peak / 1024 / 1024  # MB


def demo_memory():
    print("=" * 60)
    print("MEMORY USAGE for 100,000 instances")
    print("=" * 60)
    for cls in [NormalPoint, SlottedPoint, DataPoint]:
        mb = measure_memory(cls)
        print(f"  {cls.__name__:20s} -> {mb:.2f} MB")
    print("  Slotted ~40-50% less than Normal")


# ============================================================
# DEMO 2: __dict__ existence
# ============================================================
def demo_dict_absence():
    print("\n" + "=" * 60)
    print("__dict__ INSPECTION")
    print("=" * 60)
    n = NormalPoint(1, 2)
    s = SlottedPoint(1, 2)

    print(f"NormalPoint has __dict__   : {hasattr(n, '__dict__')}")
    print(f"SlottedPoint has __dict__  : {hasattr(s, '__dict__')}")
    print(f"NormalPoint __dict__       : {n.__dict__}")

    # Try dynamic attribute
    n.new_attr = "hello"      # works
    print(f"NormalPoint dynamic attr   : {n.new_attr}")

    try:
        s.new_attr = "hello"
    except AttributeError as e:
        print(f"SlottedPoint dynamic attr  : BLOCKED -> {e}")


# ============================================================
# DEMO 3: Speed comparison
# ============================================================
def demo_speed():
    print("\n" + "=" * 60)
    print("ATTRIBUTE ACCESS SPEED (10M ops)")
    print("=" * 60)
    n = NormalPoint(1, 2)
    s = SlottedPoint(1, 2)
    iters = 10_000_000

    start = time.perf_counter()
    for _ in range(iters):
        _ = n.x
    normal_time = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(iters):
        _ = s.x
    slot_time = time.perf_counter() - start

    print(f"  Normal access  : {normal_time:.3f}s")
    print(f"  Slotted access : {slot_time:.3f}s")
    print(f"  Speedup        : {normal_time/slot_time:.2f}x")


# ============================================================
# DEMO 4: Inheritance gotcha
# ============================================================
def demo_inheritance_gotcha():
    print("\n" + "=" * 60)
    print("INHERITANCE GOTCHA")
    print("=" * 60)

    class ParentNoSlots:
        pass

    class ChildWithSlots(ParentNoSlots):
        __slots__ = ("x",)

    c = ChildWithSlots()
    c.x = 1
    c.surprise = "Slots didn't help!"   # works — parent has __dict__
    print(f"  Child still has __dict__   : {hasattr(c, '__dict__')}")
    print(f"  c.__dict__                  : {c.__dict__}")
    print("  ❌ Lesson: ALL ancestors need __slots__")

    # Correct version
    class ParentSlots:
        __slots__ = ()

    class ChildSlots(ParentSlots):
        __slots__ = ("x",)

    c2 = ChildSlots()
    c2.x = 1
    try:
        c2.surprise = "no"
    except AttributeError:
        print("  ✅ Proper inheritance: dynamic attr blocked")


# ============================================================
# DEMO 5: Multiple inheritance conflict
# ============================================================
def demo_multi_inheritance():
    print("\n" + "=" * 60)
    print("MULTIPLE INHERITANCE")
    print("=" * 60)

    class A:
        __slots__ = ("a",)
    class B:
        __slots__ = ("b",)

    try:
        class C(A, B):
            __slots__ = ()
        print("  Created C(A, B) — unusual, depends on layout")
    except TypeError as e:
        print(f"  ❌ TypeError: {e}")


# ============================================================
# DEMO 6: Weakref + slots
# ============================================================
def demo_weakref():
    print("\n" + "=" * 60)
    print("WEAKREF + SLOTS")
    print("=" * 60)

    class NoWeakref:
        __slots__ = ("x",)

    class WithWeakref:
        __slots__ = ("x", "__weakref__")

    try:
        weakref.ref(NoWeakref())
    except TypeError as e:
        print(f"  Without __weakref__ slot: ❌ {e}")

    ref = weakref.ref(WithWeakref())
    print(f"  With __weakref__ slot   : ✅ weakref created: {ref}")


# ============================================================
# DEMO 7: Pickling slotted classes
# ============================================================
def demo_pickle():
    print("\n" + "=" * 60)
    print("PICKLING")
    print("=" * 60)
    s = SlottedPoint(10, 20)
    blob = pickle.dumps(s)
    restored = pickle.loads(blob)
    print(f"  Original   : ({s.x}, {s.y})")
    print(f"  Restored   : ({restored.x}, {restored.y})")
    print("  ✅ Pickle works fine with __slots__")


# ============================================================
# DEMO 8: Real-world simulation — particle system
# ============================================================
@dataclass(slots=True)
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    mass: float


def demo_simulation():
    print("\n" + "=" * 60)
    print("REAL-WORLD: 1M particles")
    print("=" * 60)
    n = 1_000_000
    tracemalloc.start()
    particles = [Particle(i, i, 0.0, 0.0, 1.0) for i in range(n)]
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"  1M particles (slots dataclass) : {peak/1024/1024:.1f} MB")
    print(f"  Avg per particle               : {peak/n:.1f} bytes")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_memory()
    demo_dict_absence()
    demo_speed()
    demo_inheritance_gotcha()
    demo_multi_inheritance()
    demo_weakref()
    demo_pickle()
    demo_simulation()

    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS")
    print("=" * 60)
    print("1. Use @dataclass(slots=True) in new code")
    print("2. 40-50% memory savings for data-heavy classes")
    print("3. ALL ancestors must have __slots__ to benefit")
    print("4. Add __weakref__ slot if weakref support needed")
    print("5. No multiple inheritance with conflicting layouts")
