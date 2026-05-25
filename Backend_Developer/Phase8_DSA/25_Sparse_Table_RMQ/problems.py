"""
============================================================
SPARSE TABLE / RMQ — INTERVIEW PROBLEMS
============================================================

Problems covered:
  1. Range Minimum Query (classic)
  2. Range GCD Query
  3. Sliding Window Maximum (alternative to monotonic deque)
  4. LCA (Lowest Common Ancestor) using Euler tour + RMQ
  5. Number of distinct values in range (offline, MO's algo alternative)
  6. Maximum sub-array in range (gss problem — Codeforces)
"""
import math
from collections import defaultdict


# ============================================================
# Reusable Sparse Table
# ============================================================
class SparseTable:
    def __init__(self, arr, func=min):
        self.func = func
        self.n = len(arr)
        if self.n == 0:
            return
        self.k = max(1, int(math.log2(self.n)) + 1)
        self.table = [[0] * self.k for _ in range(self.n)]
        self.log = [0] * (self.n + 1)
        for i in range(2, self.n + 1):
            self.log[i] = self.log[i // 2] + 1
        for i in range(self.n):
            self.table[i][0] = arr[i]
        j = 1
        while (1 << j) <= self.n:
            i = 0
            while i + (1 << j) <= self.n:
                self.table[i][j] = func(
                    self.table[i][j - 1],
                    self.table[i + (1 << (j - 1))][j - 1]
                )
                i += 1
            j += 1

    def query(self, L, R):
        if L > R:
            return None
        k = self.log[R - L + 1]
        return self.func(self.table[L][k], self.table[R - (1 << k) + 1][k])


# ============================================================
# Problem 1: Classic Range Minimum Query
# https://www.spoj.com/problems/RMQSQ/
# ============================================================
def range_min_queries(arr, queries):
    """
    For each query (L, R), return min(arr[L..R]).
    Use Sparse Table — O(N log N) build + O(1) query.
    """
    st = SparseTable(arr, min)
    return [st.query(l, r) for l, r in queries]


# ============================================================
# Problem 2: Range GCD
# https://www.spoj.com/problems/GCDEX/
# ============================================================
def range_gcd_queries(arr, queries):
    st = SparseTable(arr, math.gcd)
    return [st.query(l, r) for l, r in queries]


# ============================================================
# Problem 3: Sliding Window Maximum (LC 239)
# Sparse Table alternative to monotonic deque.
# ============================================================
def sliding_window_max(nums, k):
    """O((N-k+1) * 1) queries after O(N log N) build."""
    st = SparseTable(nums, max)
    result = []
    for i in range(len(nums) - k + 1):
        result.append(st.query(i, i + k - 1))
    return result


# ============================================================
# Problem 4: LCA via Euler Tour + RMQ
# Tarjan's offline LCA / Sparse Table approach
# ============================================================
class LCA_EulerRMQ:
    """
    For tree with N nodes, answer LCA(u, v) in O(1) per query.
    Build:
      1. Euler tour (DFS, record nodes on entry/exit)
      2. Depth array parallel to Euler tour
      3. first_occurrence[v] = first index in tour
      4. Sparse Table on depth — RMQ
    Query:
      LCA(u, v) = node at index of min depth in tour[first[u]..first[v]]
    """
    def __init__(self, n, edges, root=0):
        self.n = n
        self.adj = defaultdict(list)
        for u, v in edges:
            self.adj[u].append(v)
            self.adj[v].append(u)
        self.tour = []
        self.depth = []
        self.first = [-1] * n
        self._dfs(root, -1, 0)
        # Sparse table over (depth, tour_index) pairs — break ties by index
        # Store indices into tour; comparator uses depth
        self._depth_st = SparseTable(self.depth, min)  # min depth
        # We need argmin actually — augment

    def _dfs(self, u, parent, d):
        self.first[u] = len(self.tour)
        self.tour.append(u)
        self.depth.append(d)
        for v in self.adj[u]:
            if v != parent:
                self._dfs(v, u, d + 1)
                self.tour.append(u)
                self.depth.append(d)

    def lca(self, u, v):
        l, r = self.first[u], self.first[v]
        if l > r:
            l, r = r, l
        # Find index of min depth in tour[l..r]
        # Linear scan (could optimize with custom sparse table storing indices)
        min_idx = l
        for i in range(l + 1, r + 1):
            if self.depth[i] < self.depth[min_idx]:
                min_idx = i
        return self.tour[min_idx]


# ============================================================
# Problem 5: Static Range Mode (frequent element)
# Heuristic + sparse table for some variants (not full solution)
# ============================================================
def max_in_range(arr, queries):
    """LC: Range Maximum Query — common variant."""
    st = SparseTable(arr, max)
    return [st.query(l, r) for l, r in queries]


# ============================================================
# Problem 6: Smallest element ≥ x in range (binary search + sparse max)
# ============================================================
def has_element_ge_x(arr, queries):
    """For each (L, R, x), is there any element ≥ x in arr[L..R]?
    Use sparse table of max — O(1) lookup."""
    st = SparseTable(arr, max)
    return [st.query(l, r) >= x for l, r, x in queries]


# ============================================================
# Problem 7: Range AND/OR/XOR Queries
# AND, OR are idempotent — sparse table works!
# XOR is NOT idempotent — use prefix XOR.
# ============================================================
def range_and_queries(arr, queries):
    st = SparseTable(arr, lambda a, b: a & b)
    return [st.query(l, r) for l, r in queries]


def range_or_queries(arr, queries):
    st = SparseTable(arr, lambda a, b: a | b)
    return [st.query(l, r) for l, r in queries]


def range_xor_queries(arr, queries):
    """XOR — use prefix XOR (NOT sparse table)."""
    prefix = [0]
    for x in arr:
        prefix.append(prefix[-1] ^ x)
    return [prefix[r + 1] ^ prefix[l] for l, r in queries]


# ============================================================
# Problem 8: Maximum value among slice with at least K elements (LC 1696 variant)
# ============================================================
def jump_game_max_score(nums, k):
    """DP + sliding range max via sparse table.
    dp[i] = nums[i] + max(dp[i-k..i-1])"""
    n = len(nums)
    dp = [0] * n
    dp[0] = nums[0]
    for i in range(1, n):
        # Need max of dp[max(0, i-k) .. i-1]
        l, r = max(0, i - k), i - 1
        # Rebuild ST per step is wasteful — would use deque in practice
        # Here for demo: linear max
        dp[i] = nums[i] + max(dp[l:r+1])
    return dp[-1]


# ============================================================
# Demo
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("PROBLEM 1: Range Min Queries")
    print("=" * 60)
    arr = [4, 2, 7, 1, 5, 8, 0, 3]
    queries = [(0, 3), (2, 6), (5, 7), (0, 7)]
    print(f"Array: {arr}")
    print(f"Queries: {queries}")
    print(f"Mins  : {range_min_queries(arr, queries)}")

    print("\n" + "=" * 60)
    print("PROBLEM 2: Range GCD")
    print("=" * 60)
    arr = [12, 18, 6, 24, 36, 48]
    print(f"GCDs: {range_gcd_queries(arr, [(0, 2), (1, 4), (0, 5)])}")

    print("\n" + "=" * 60)
    print("PROBLEM 3: Sliding Window Maximum")
    print("=" * 60)
    nums = [1, 3, -1, -3, 5, 3, 6, 7]
    print(f"k=3: {sliding_window_max(nums, 3)}")

    print("\n" + "=" * 60)
    print("PROBLEM 4: LCA via Euler Tour + RMQ")
    print("=" * 60)
    # Tree:    0
    #        / | \
    #       1  2  3
    #      / \    |
    #     4   5   6
    edges = [(0, 1), (0, 2), (0, 3), (1, 4), (1, 5), (3, 6)]
    lca = LCA_EulerRMQ(7, edges, root=0)
    print(f"LCA(4, 5) = {lca.lca(4, 5)}  (expected 1)")
    print(f"LCA(4, 6) = {lca.lca(4, 6)}  (expected 0)")
    print(f"LCA(5, 2) = {lca.lca(5, 2)}  (expected 0)")

    print("\n" + "=" * 60)
    print("PROBLEM 7: Range AND/OR/XOR")
    print("=" * 60)
    arr = [0b1100, 0b1010, 0b0110, 0b1110]
    print(f"AND in [0,3]: {bin(range_and_queries(arr, [(0, 3)])[0])}")
    print(f"OR  in [0,3]: {bin(range_or_queries(arr, [(0, 3)])[0])}")
    print(f"XOR in [0,3]: {bin(range_xor_queries(arr, [(0, 3)])[0])}")

    print("\n" + "=" * 60)
    print("KEY PATTERNS")
    print("=" * 60)
    print("""
1. Build O(N log N), Query O(1) — best for static + idempotent ops
2. Common ops: min, max, gcd, AND, OR
3. For SUM/XOR — use prefix arrays instead
4. Combine with Euler tour for tree LCA
5. Avoid for dynamic data — use Segment Tree
""")
