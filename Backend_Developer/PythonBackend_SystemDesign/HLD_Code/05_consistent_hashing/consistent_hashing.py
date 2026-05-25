"""
============================================================
CONSISTENT HASHING — Working Implementation
============================================================
Used by: Cassandra, DynamoDB, Memcached, Riak, Couchbase

WHY?
----
Naive hashing:  key % N_nodes
  When nodes change (add/remove), MOST keys must move.
  100 keys, 4 nodes → add 5th node → ~75% remap.

Consistent hashing:
  Only K/N keys move when adding/removing a node.
  100 keys, 4 nodes → add 5th node → ~20% remap.

ALGORITHM:
1. Hash all nodes onto a RING (0 to 2^32 - 1)
2. Hash keys onto same ring
3. Key belongs to the FIRST node CLOCKWISE from its position
4. Add/remove node = only affects neighboring keys

VIRTUAL NODES (vnodes):
- Each physical node placed at MULTIPLE positions on the ring
- Smooths out load distribution (real life: 100-500 vnodes per node)
- Without vnodes: large variance in load per node

Run: python consistent_hashing.py
"""
from __future__ import annotations
import hashlib
import bisect
from dataclasses import dataclass
from collections import defaultdict, Counter


# ============================================================
# 1. BASIC CONSISTENT HASHING (no virtual nodes)
# ============================================================
class BasicConsistentHash:
    """One position per node on the ring."""
    def __init__(self):
        self._ring: dict[int, str] = {}      # hash → node
        self._sorted_hashes: list[int] = []  # for bisect

    def _hash(self, key: str) -> int:
        h = hashlib.md5(key.encode()).digest()
        return int.from_bytes(h[:4], "big")   # 32-bit hash

    def add_node(self, node: str):
        h = self._hash(node)
        self._ring[h] = node
        bisect.insort(self._sorted_hashes, h)

    def remove_node(self, node: str):
        h = self._hash(node)
        if h in self._ring:
            del self._ring[h]
            self._sorted_hashes.remove(h)

    def get_node(self, key: str) -> str | None:
        if not self._ring:
            return None
        h = self._hash(key)
        # Find first node ≥ h (clockwise)
        idx = bisect.bisect_right(self._sorted_hashes, h)
        if idx == len(self._sorted_hashes):
            idx = 0   # wrap around
        return self._ring[self._sorted_hashes[idx]]


# ============================================================
# 2. CONSISTENT HASHING WITH VIRTUAL NODES (production-grade)
# ============================================================
class ConsistentHashRing:
    """
    Production-grade: each physical node maps to N virtual nodes.
    Replication factor controls how many nodes a key replicates to.
    """
    def __init__(self, virtual_nodes_per_node: int = 100, replication: int = 1):
        self.vnodes = virtual_nodes_per_node
        self.replication = replication
        self._ring: dict[int, str] = {}       # hash → physical node name
        self._sorted: list[int] = []
        self._physical_nodes: set[str] = set()

    def _hash(self, key: str) -> int:
        h = hashlib.md5(key.encode()).digest()
        return int.from_bytes(h[:4], "big")

    def _vnode_key(self, node: str, i: int) -> str:
        return f"{node}#{i}"

    def add_node(self, node: str):
        if node in self._physical_nodes:
            return
        self._physical_nodes.add(node)
        for i in range(self.vnodes):
            h = self._hash(self._vnode_key(node, i))
            self._ring[h] = node
            bisect.insort(self._sorted, h)

    def remove_node(self, node: str):
        if node not in self._physical_nodes:
            return
        self._physical_nodes.discard(node)
        for i in range(self.vnodes):
            h = self._hash(self._vnode_key(node, i))
            if h in self._ring:
                del self._ring[h]
                self._sorted.remove(h)

    def get_node(self, key: str) -> str | None:
        """Primary node for a key."""
        if not self._ring:
            return None
        h = self._hash(key)
        idx = bisect.bisect_right(self._sorted, h) % len(self._sorted)
        return self._ring[self._sorted[idx]]

    def get_nodes(self, key: str, count: int | None = None) -> list[str]:
        """Get N distinct physical nodes (for replication)."""
        if not self._ring:
            return []
        n = count or self.replication
        h = self._hash(key)
        idx = bisect.bisect_right(self._sorted, h) % len(self._sorted)
        result: list[str] = []
        seen: set[str] = set()
        for _ in range(len(self._sorted)):
            node = self._ring[self._sorted[idx]]
            if node not in seen:
                seen.add(node)
                result.append(node)
                if len(result) == n:
                    break
            idx = (idx + 1) % len(self._sorted)
        return result

    @property
    def nodes(self) -> list[str]:
        return sorted(self._physical_nodes)


# ============================================================
# 3. DEMO: Remap impact comparison
# ============================================================
def demo_remap_impact():
    print("=" * 60)
    print("DEMO 1: Add Node — measure key remap")
    print("=" * 60)

    keys = [f"key_{i}" for i in range(10000)]

    # Without vnodes
    basic = BasicConsistentHash()
    for n in ["node1", "node2", "node3", "node4"]:
        basic.add_node(n)
    before = {k: basic.get_node(k) for k in keys}
    basic.add_node("node5")
    after = {k: basic.get_node(k) for k in keys}
    moved_basic = sum(1 for k in keys if before[k] != after[k])

    # With vnodes
    ring = ConsistentHashRing(virtual_nodes_per_node=100)
    for n in ["node1", "node2", "node3", "node4"]:
        ring.add_node(n)
    before2 = {k: ring.get_node(k) for k in keys}
    ring.add_node("node5")
    after2 = {k: ring.get_node(k) for k in keys}
    moved_vnodes = sum(1 for k in keys if before2[k] != after2[k])

    # Naive `key % N`
    def naive(k, n): return f"node{hash(k) % n}"
    moved_naive = sum(1 for k in keys if naive(k, 4) != naive(k, 5))

    print(f"  10,000 keys; add 5th node:")
    print(f"    Naive %N      : {moved_naive:5d} keys moved ({moved_naive/100:.1f}%) ❌")
    print(f"    Basic CH      : {moved_basic:5d} keys moved ({moved_basic/100:.1f}%)")
    print(f"    CH + 100 vnodes: {moved_vnodes:5d} keys moved ({moved_vnodes/100:.1f}%) ✅")


# ============================================================
# 4. DEMO: Load distribution comparison
# ============================================================
def demo_load_distribution():
    print("\n" + "=" * 60)
    print("DEMO 2: Load distribution (no vnodes vs vnodes)")
    print("=" * 60)

    keys = [f"key_{i}" for i in range(10000)]
    nodes = ["n1", "n2", "n3", "n4", "n5"]

    # Without vnodes
    basic = BasicConsistentHash()
    for n in nodes: basic.add_node(n)
    dist_basic = Counter(basic.get_node(k) for k in keys)

    # With 100 vnodes
    ring100 = ConsistentHashRing(virtual_nodes_per_node=100)
    for n in nodes: ring100.add_node(n)
    dist_100 = Counter(ring100.get_node(k) for k in keys)

    # With 500 vnodes
    ring500 = ConsistentHashRing(virtual_nodes_per_node=500)
    for n in nodes: ring500.add_node(n)
    dist_500 = Counter(ring500.get_node(k) for k in keys)

    print(f"  Ideal per-node: {10000//len(nodes)} keys")
    print(f"  {'Node':<6} {'No vnodes':<12} {'100 vnodes':<12} {'500 vnodes':<12}")
    for n in nodes:
        print(f"  {n:<6} {dist_basic[n]:<12} {dist_100[n]:<12} {dist_500[n]:<12}")

    def variance(d):
        avg = sum(d.values()) / len(d)
        return sum((v - avg) ** 2 for v in d.values()) ** 0.5 / avg

    print(f"\n  Variance:")
    print(f"    No vnodes : {variance(dist_basic):.3f}")
    print(f"    100 vnodes: {variance(dist_100):.3f}")
    print(f"    500 vnodes: {variance(dist_500):.3f}")


# ============================================================
# 5. DEMO: Replication
# ============================================================
def demo_replication():
    print("\n" + "=" * 60)
    print("DEMO 3: Replication — N copies per key")
    print("=" * 60)
    ring = ConsistentHashRing(virtual_nodes_per_node=100, replication=3)
    for n in ["n1", "n2", "n3", "n4", "n5"]:
        ring.add_node(n)

    for key in ["user:42", "session:abc", "cache:items"]:
        replicas = ring.get_nodes(key)
        print(f"  {key:18s} → primary={replicas[0]}, replicas={replicas[1:]}")


# ============================================================
# 6. DEMO: Removing a node
# ============================================================
def demo_remove_node():
    print("\n" + "=" * 60)
    print("DEMO 4: Remove node — only keys on that node move")
    print("=" * 60)
    ring = ConsistentHashRing(virtual_nodes_per_node=100)
    for n in ["n1", "n2", "n3", "n4"]:
        ring.add_node(n)

    keys = [f"key_{i}" for i in range(10000)]
    before = {k: ring.get_node(k) for k in keys}

    ring.remove_node("n2")
    after = {k: ring.get_node(k) for k in keys}

    moved = sum(1 for k in keys if before[k] != after[k])
    on_n2 = sum(1 for k in keys if before[k] == "n2")

    print(f"  Total moved: {moved} (was on n2: {on_n2})")
    print(f"  → Only keys previously on n2 redistributed to others")

    # Distribution after removal
    dist = Counter(after.values())
    print(f"\n  New distribution: {dict(dist)}")


# ============================================================
# 7. CACHE CLIENT EXAMPLE (real-world wrapper)
# ============================================================
class DistributedCache:
    """Memcached-style client using consistent hashing."""
    def __init__(self, replication=2):
        self.ring = ConsistentHashRing(virtual_nodes_per_node=200, replication=replication)
        self._nodes: dict[str, dict] = defaultdict(dict)   # node → kv store

    def add_node(self, node: str):
        self.ring.add_node(node)

    def remove_node(self, node: str):
        self.ring.remove_node(node)

    def set(self, key: str, value):
        for node in self.ring.get_nodes(key):
            self._nodes[node][key] = value
        return self.ring.get_nodes(key)

    def get(self, key: str):
        # Try primary, fallback to replicas
        for node in self.ring.get_nodes(key):
            if key in self._nodes[node]:
                return self._nodes[node][key], node
        return None, None

    def stats(self) -> dict:
        return {n: len(kv) for n, kv in self._nodes.items()}


def demo_distributed_cache():
    print("\n" + "=" * 60)
    print("DEMO 5: Distributed Cache Client")
    print("=" * 60)
    cache = DistributedCache(replication=2)
    for n in ["cache-1", "cache-2", "cache-3"]:
        cache.add_node(n)

    # Insert 1000 keys
    for i in range(1000):
        cache.set(f"k_{i}", f"v_{i}")

    print(f"  Per-node storage: {cache.stats()}")
    # Each key has 2 replicas → total stored = 2000 across 3 nodes

    # Reading
    val, node = cache.get("k_42")
    print(f"  GET k_42 → '{val}' from {node}")

    # Simulate node failure
    print("\n  Simulating cache-2 going down...")
    cache.remove_node("cache-2")

    misses = 0
    for i in range(1000):
        val, _ = cache.get(f"k_{i}")
        if val is None:
            misses += 1
    print(f"  Misses after node removal: {misses}/1000 (replication saved most)")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_remap_impact()
    demo_load_distribution()
    demo_replication()
    demo_remove_node()
    demo_distributed_cache()

    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS")
    print("=" * 60)
    print("""
1. Hash function: MD5/SHA1 commonly used (cryptographic strength
   not required — just uniform distribution).

2. Virtual nodes are ESSENTIAL — without them, load distribution
   is uneven (large variance).

3. Common vnode counts:
   - 100-200: typical (cassandra default ~256)
   - 500-1000: very high replication needs
   - More vnodes = better balance, more memory

4. Replication factor: 2-3 typical. Trade-off:
   - More replicas = better availability, more storage
   - Less replicas = cheaper but more data loss risk

5. Adding node: K/N keys move (K = total keys, N = nodes)
   Removing node: only keys on that node move

6. Production tools using consistent hashing:
   - Memcached client libraries (libmemcached, pylibmc)
   - Cassandra (uses 256 vnodes by default)
   - DynamoDB (Amazon's storage)
   - Riak, Voldemort
   - HAProxy (sticky sessions)

7. Variants:
   - Jump consistent hash (Google) — no ring storage
   - Rendezvous (HRW) hashing — alternative approach
   - Maglev (Google) — for load balancers
""")
