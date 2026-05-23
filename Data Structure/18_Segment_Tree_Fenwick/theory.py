"""
18 — Segment Tree & Fenwick Tree (BIT) — Theory
================================================
Level: Advanced
"""
from __future__ import annotations
from typing import List
import math

# ════════════════════════════════════════════════════════════
# WHAT & WHY
# ════════════════════════════════════════════════════════════
"""
PROBLEM: Given an array, support two operations efficiently:
  1. Point update: change a[i]
  2. Range query: sum/min/max of a[l..r]

NAIVE:
  update O(1), query O(n) — bad for many queries
  prefix sum: query O(1), update O(n) — bad for many updates

SOLUTION: Segment Tree or Fenwick Tree → both O(log n) for update AND query.
"""

# ════════════════════════════════════════════════════════════
# COMPLEXITY
# ════════════════════════════════════════════════════════════
"""
Structure              Build       Query      Update     Space
────────────────────────────────────────────────────────────────
Naive array            O(1)        O(n)       O(1)       O(n)
Prefix sum             O(n)        O(1)       O(n)       O(n)
Segment Tree           O(n)        O(log n)   O(log n)   O(4n)
Fenwick Tree (BIT)     O(n)        O(log n)   O(log n)   O(n)
Sparse Table (RMQ)     O(n log n)  O(1)       N/A        O(n log n)

Segment Tree with Lazy Propagation:
  Range update + range query: O(log n) each
"""

# ════════════════════════════════════════════════════════════
# SEGMENT TREE — Array-based, 1-indexed internal nodes
# ════════════════════════════════════════════════════════════

class SegmentTree:
    """
    Generic Segment Tree for range sum queries + point updates.
    Internal array size = 4 * n (safe upper bound).
    Nodes: root=0, left child=2i+1, right child=2i+2.
    """
    def __init__(self, nums: List[int]):
        self.n = len(nums)
        self.tree = [0] * (4 * self.n)
        if nums:
            self._build(nums, 0, 0, self.n - 1)

    def _build(self, nums: List[int], node: int, start: int, end: int) -> None:
        if start == end:
            self.tree[node] = nums[start]
        else:
            mid = (start + end) // 2
            self._build(nums, 2 * node + 1, start, mid)
            self._build(nums, 2 * node + 2, mid + 1, end)
            self.tree[node] = self.tree[2*node+1] + self.tree[2*node+2]

    def update(self, idx: int, val: int, node: int = 0, start: int = 0, end: int = -1) -> None:
        """Point update: set a[idx] = val. O(log n)."""
        if end == -1: end = self.n - 1
        if start == end:
            self.tree[node] = val
            return
        mid = (start + end) // 2
        if idx <= mid:
            self.update(idx, val, 2*node+1, start, mid)
        else:
            self.update(idx, val, 2*node+2, mid+1, end)
        self.tree[node] = self.tree[2*node+1] + self.tree[2*node+2]

    def query(self, l: int, r: int, node: int = 0, start: int = 0, end: int = -1) -> int:
        """Range sum query [l..r]. O(log n)."""
        if end == -1: end = self.n - 1
        if r < start or end < l:
            return 0        # out of range (identity for sum)
        if l <= start and end <= r:
            return self.tree[node]   # fully inside query range
        mid = (start + end) // 2
        return (self.query(l, r, 2*node+1, start, mid) +
                self.query(l, r, 2*node+2, mid+1, end))

# Demo
st = SegmentTree([1, 3, 5, 7, 9, 11])
print("ST query [1,3]:", st.query(1, 3))  # 3+5+7 = 15
st.update(1, 10)
print("ST query [1,3] after update:", st.query(1, 3))  # 10+5+7 = 22


# ════════════════════════════════════════════════════════════
# SEGMENT TREE WITH LAZY PROPAGATION
# (Range update + Range query)
# ════════════════════════════════════════════════════════════

class LazySegmentTree:
    """
    Supports range add update + range sum query.
    Lazy array defers pending updates to children.
    """
    def __init__(self, nums: List[int]):
        self.n = len(nums)
        self.tree = [0] * (4 * self.n)
        self.lazy = [0] * (4 * self.n)
        self._build(nums, 0, 0, self.n - 1)

    def _build(self, nums, node, start, end):
        if start == end:
            self.tree[node] = nums[start]
        else:
            mid = (start + end) // 2
            self._build(nums, 2*node+1, start, mid)
            self._build(nums, 2*node+2, mid+1, end)
            self.tree[node] = self.tree[2*node+1] + self.tree[2*node+2]

    def _push_down(self, node, start, end):
        if self.lazy[node] != 0:
            mid = (start + end) // 2
            # Apply lazy to children
            left, right = 2*node+1, 2*node+2
            self.tree[left]  += self.lazy[node] * (mid - start + 1)
            self.tree[right] += self.lazy[node] * (end - mid)
            self.lazy[left]  += self.lazy[node]
            self.lazy[right] += self.lazy[node]
            self.lazy[node] = 0

    def range_update(self, l, r, val, node=0, start=0, end=-1):
        """Add val to all elements in [l..r]. O(log n)."""
        if end == -1: end = self.n - 1
        if r < start or end < l: return
        if l <= start and end <= r:
            self.tree[node] += val * (end - start + 1)
            self.lazy[node] += val
            return
        self._push_down(node, start, end)
        mid = (start + end) // 2
        self.range_update(l, r, val, 2*node+1, start, mid)
        self.range_update(l, r, val, 2*node+2, mid+1, end)
        self.tree[node] = self.tree[2*node+1] + self.tree[2*node+2]

    def range_query(self, l, r, node=0, start=0, end=-1):
        """Sum of [l..r]. O(log n)."""
        if end == -1: end = self.n - 1
        if r < start or end < l: return 0
        if l <= start and end <= r: return self.tree[node]
        self._push_down(node, start, end)
        mid = (start + end) // 2
        return (self.range_query(l, r, 2*node+1, start, mid) +
                self.range_query(l, r, 2*node+2, mid+1, end))

lst = LazySegmentTree([1, 2, 3, 4, 5])
print("Lazy ST sum [0,4]:", lst.range_query(0, 4))  # 15
lst.range_update(1, 3, 10)   # add 10 to indices 1,2,3
print("After +10 to [1,3], sum [0,4]:", lst.range_query(0, 4))  # 15+30=45


# ════════════════════════════════════════════════════════════
# FENWICK TREE (Binary Indexed Tree)
# ════════════════════════════════════════════════════════════

class FenwickTree:
    """
    1-indexed. Supports:
      - Point update (add delta to position i)
      - Prefix sum query [1..i]

    KEY TRICK: i & (-i) gives the lowest set bit of i.
    - update: add to i, then move to next responsible node: i += i & (-i)
    - prefix_sum: add tree[i], then remove lowest bit: i -= i & (-i)
    """
    def __init__(self, n: int):
        self.n = n
        self.tree = [0] * (n + 1)  # 1-indexed

    def update(self, i: int, delta: int) -> None:
        """Add delta to position i (1-indexed). O(log n)."""
        while i <= self.n:
            self.tree[i] += delta
            i += i & (-i)    # move to parent (next responsible node)

    def prefix_sum(self, i: int) -> int:
        """Sum of positions [1..i]. O(log n)."""
        total = 0
        while i > 0:
            total += self.tree[i]
            i -= i & (-i)    # remove lowest set bit
        return total

    def range_sum(self, l: int, r: int) -> int:
        """Sum of positions [l..r] (1-indexed). O(log n)."""
        return self.prefix_sum(r) - self.prefix_sum(l - 1)

    def build(self, nums: List[int]) -> None:
        """Build from 0-indexed array. O(n log n)."""
        for i, v in enumerate(nums, 1):
            self.update(i, v)

    @classmethod
    def from_list(cls, nums: List[int]) -> 'FenwickTree':
        ft = cls(len(nums))
        ft.build(nums)
        return ft

# Demo
ft = FenwickTree.from_list([1, 3, 5, 7, 9, 11])
print("FT prefix_sum(3):", ft.prefix_sum(3))   # 1+3+5 = 9
print("FT range_sum(2,4):", ft.range_sum(2,4)) # 3+5+7 = 15
ft.update(2, 2)   # add 2 to position 2 (now 3→5)
print("FT after update, range_sum(2,4):", ft.range_sum(2,4))  # 5+5+7 = 17


# ════════════════════════════════════════════════════════════
# 2D FENWICK TREE
# ════════════════════════════════════════════════════════════

class FenwickTree2D:
    """2D BIT for matrix range sum queries + point updates."""
    def __init__(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        self.tree = [[0] * (cols + 1) for _ in range(rows + 1)]

    def update(self, r: int, c: int, delta: int) -> None:
        i = r
        while i <= self.rows:
            j = c
            while j <= self.cols:
                self.tree[i][j] += delta
                j += j & (-j)
            i += i & (-i)

    def prefix_sum(self, r: int, c: int) -> int:
        total = 0
        i = r
        while i > 0:
            j = c
            while j > 0:
                total += self.tree[i][j]
                j -= j & (-j)
            i -= i & (-i)
        return total

    def range_sum(self, r1, c1, r2, c2) -> int:
        return (self.prefix_sum(r2, c2)
              - self.prefix_sum(r1-1, c2)
              - self.prefix_sum(r2, c1-1)
              + self.prefix_sum(r1-1, c1-1))


# ════════════════════════════════════════════════════════════
# SPARSE TABLE — O(1) Range Minimum Query (static array)
# ════════════════════════════════════════════════════════════

class SparseTable:
    """
    Range Minimum Query in O(1) after O(n log n) preprocessing.
    ONLY works for idempotent operations (min, max, gcd) — NOT sum.
    Array must be STATIC (no updates).

    Idea: table[j][i] = min of 2^j elements starting at i.
    Query [l,r]: two overlapping windows of size k=log2(r-l+1).
    min(table[k][l], table[k][r - 2^k + 1]) = answer.
    """
    def __init__(self, nums: List[int]):
        n = len(nums)
        if n == 0: return
        k = int(math.log2(n)) + 1
        self.table = [[float('inf')] * n for _ in range(k)]
        self.table[0] = nums[:]
        self.log2 = [0] * (n + 1)
        for i in range(2, n + 1):
            self.log2[i] = self.log2[i // 2] + 1
        j = 1
        while (1 << j) <= n:
            for i in range(n - (1 << j) + 1):
                self.table[j][i] = min(
                    self.table[j-1][i],
                    self.table[j-1][i + (1 << (j-1))]
                )
            j += 1

    def query_min(self, l: int, r: int) -> int:
        """O(1) range minimum query."""
        j = self.log2[r - l + 1]
        return min(self.table[j][l], self.table[j][r - (1 << j) + 1])

sp = SparseTable([2, 4, 3, 1, 6, 7, 8, 9, 1, 7])
print("Sparse Table min [0,4]:", sp.query_min(0, 4))   # 1
print("Sparse Table min [3,7]:", sp.query_min(3, 7))   # 1


# ════════════════════════════════════════════════════════════
# WHEN TO USE WHICH
# ════════════════════════════════════════════════════════════
"""
Use FENWICK TREE when:
  ✅ Only need prefix sum / range sum
  ✅ Point updates only (not range updates)
  ✅ Want simpler code
  ✅ 1D or 2D sum queries

Use SEGMENT TREE when:
  ✅ Need min, max, gcd, or any associative operation
  ✅ Need range updates (use lazy propagation)
  ✅ Need to store additional info per node
  ✅ More complex queries (count inversions, find kth element)

Use SPARSE TABLE when:
  ✅ Array is STATIC (no updates)
  ✅ Need O(1) range minimum/maximum queries
  ✅ Can afford O(n log n) preprocessing + O(n log n) space
"""

# ════════════════════════════════════════════════════════════
# INTERVIEW Q&A
# ════════════════════════════════════════════════════════════
"""
Q1: What does i & (-i) mean in Fenwick Tree?
A: (-i) in two's complement = ~i + 1 = flip bits of i, add 1.
   i & (-i) isolates the lowest set bit of i.
   Example: i=6 (110), -i=010 (two's complement), 6&-6 = 010 = 2.
   This determines the "range" each node is responsible for.

Q2: Why is Segment Tree array size 4n?
A: In worst case (n not power of 2), the tree can have up to 4n nodes.
   Safe allocation. Actual nodes used ≈ 2n for power-of-2 sizes.

Q3: What is lazy propagation?
A: Defer range updates to children. Store pending update in lazy[].
   Before accessing children, push down lazy value.
   Allows O(log n) range updates (instead of O(n) naive).

Q4: Can Fenwick Tree do range updates?
A: Yes, with a trick: maintain a difference BIT. Range add [l,r] +val:
   update(l, val), update(r+1, -val). Point query = prefix_sum(i).
   For range sum + range update: need TWO BITs.

Q5: Why can't Sparse Table be used for sum queries?
A: Sparse Table uses overlapping windows: table[k][l] and table[k][r-2^k+1].
   For min/max, overlap doesn't matter (idempotent: min(a,a)=a).
   For sum, overlap would double-count elements. ❌

Q6: What is coordinate compression? When needed with Segment Tree?
A: If values are large (1 to 10^9) but count is small (n ≤ 10^5),
   map values to [0,n-1] range. Then build Segment Tree on compressed values.
   Used in: Count of Smaller Numbers After Self, Count of Range Sum.

Q7: Segment Tree vs Fenwick for LC 307 (Range Sum Query Mutable)?
A: Both work. Fenwick is simpler and slightly faster (smaller constant).
   Segment Tree is more general (easy to adapt for min/max).

Q8: How to find kth smallest with Fenwick Tree?
A: Binary search on Fenwick Tree. Start from MSB, greedily descend.
   O(log^2 n) with binary search, O(log n) with BIT walk.

Q9: Time complexity of building Segment Tree?
A: O(n) — each of the n leaves is visited once, each internal node
   is computed once from its two children. Total: O(2n) = O(n).

Q10: What is a Persistent Segment Tree?
A: Each update creates a new root (version) but shares unchanged nodes
   with previous version. Space O(n log n). Allows querying historical versions.
   Used for: range kth smallest on queries, versioned data structures.
"""
