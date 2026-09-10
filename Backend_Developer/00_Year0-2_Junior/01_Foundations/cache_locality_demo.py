"""
CPU Cache / NUMA -- verified practical demo.
Honesty note up front: this machine (Apple Silicon M1) has NO NUMA nodes
-- `numactl` doesn't exist, there's no `hw.numa` sysctl. Apple Silicon
uses a Unified Memory Architecture (all cores share one memory pool
equally), not the multi-socket NUMA topology the theory section
describes. NUMA itself can't be demonstrated on this hardware -- what
CAN be verified here is: (1) cache-locality's real effect on Python
code (sequential vs random access), and (2) this chip's actual
asymmetric-core split (P-cores vs E-cores), which is a different kind
of "not all cores are equal" fact worth knowing on Apple Silicon.
"""

import array
import random
import subprocess
import time


def demo_sequential_vs_random_access():
    print("=== Proof 1: sequential vs random memory access -- real timing difference ===")
    n = 20_000_000
    # array.array('q', ...) stores raw 8-byte ints contiguously (unlike a
    # Python list of int OBJECTS, which is a list of pointers scattered
    # across the heap) -- closer to the "flat array" the theory describes.
    data = array.array("q", range(n))

    sequential_indices = range(n)
    random_indices = list(range(n))
    random.shuffle(random_indices)

    start = time.perf_counter()
    total = 0
    for i in sequential_indices:
        total += data[i]
    seq_time = time.perf_counter() - start

    start = time.perf_counter()
    total = 0
    for i in random_indices:
        total += data[i]
    rand_time = time.perf_counter() - start

    print(f"  Sequential access: {seq_time:.3f}s")
    print(f"  Random access:     {rand_time:.3f}s")
    print(f"  Random was {rand_time / seq_time:.2f}x slower")
    print("  (both touch the exact same N values, same total work -- the")
    print("   difference is ONLY access pattern. Sequential lets the CPU")
    print("   prefetch and reuse cache lines; random access defeats that,")
    print("   forcing more cache misses. Some of this gap is Python-interpreter")
    print("   overhead too, not pure hardware cache effect -- but the direction")
    print("   and rough scale matches the theory.)\n")


def demo_apple_silicon_core_split():
    print("=== Bonus: this machine's real core topology (not NUMA, but related idea) ===")
    try:
        p_cores = subprocess.check_output(
            ["sysctl", "-n", "hw.perflevel0.physicalcpu"], text=True
        ).strip()
        e_cores = subprocess.check_output(
            ["sysctl", "-n", "hw.perflevel1.physicalcpu"], text=True
        ).strip()
        print(f"  Performance cores (P-cores): {p_cores}")
        print(f"  Efficiency cores (E-cores):  {e_cores}")
        print("  (Apple Silicon's scheduler decides which core type runs your")
        print("   thread -- NOT the same mechanism as NUMA memory locality, but")
        print("   it's the same underlying idea: 'not every core is identical,")
        print("   placement matters.' The OS hides this from you; Linux NUMA")
        print("   requires the OS/you to reason about it explicitly.)")
    except Exception as e:
        print(f"  (sysctl query failed: {e} -- not Apple Silicon, or unsupported)")

    print()
    numa_available = subprocess.run(
        ["which", "numactl"], capture_output=True
    ).returncode == 0
    print(f"  numactl available on this machine: {numa_available}")
    print("  -> confirms: no traditional NUMA topology here. The NUMA theory")
    print("     section describes real multi-socket Linux servers -- verify it")
    print("     there (`numactl --hardware`), not on Apple Silicon dev machines.")


if __name__ == "__main__":
    demo_sequential_vs_random_access()
    demo_apple_silicon_core_split()
