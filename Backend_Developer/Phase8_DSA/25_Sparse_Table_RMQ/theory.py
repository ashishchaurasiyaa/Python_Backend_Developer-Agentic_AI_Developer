"""
============================================================
SPARSE TABLE & RANGE MINIMUM QUERY (RMQ)
============================================================

WHAT IS IT?
-----------
Sparse Table = data structure for answering RANGE QUERIES on an
IMMUTABLE array in O(1) time after O(N log N) preprocessing.

Best for: IDEMPOTENT operations — min, max, gcd, AND, OR.
NOT for: sum (use prefix sum), updates (use segment tree).

WHEN TO USE WHICH?
-------------------
| Structure       | Build   | Query  | Update | Operations   |
|-----------------|---------|--------|--------|--------------|
| Prefix Sum      | O(N)    | O(1)   | O(N)   | sum          |
| Sparse Table    | O(NlogN)| O(1)   | NA     | min/max/gcd  |
| Segment Tree    | O(N)    | O(logN)| O(logN)| ANY          |
| Fenwick (BIT)   | O(N)    | O(logN)| O(logN)| sum/xor      |
| Sqrt Decomp     | O(N)    | O(√N)  | O(√N)  | ANY          |

KEY INSIGHT
-----------
Any range [L, R] of length k can be covered by 2 overlapping
power-of-2 ranges. For MIN/MAX, overlap doesn't hurt (idempotent).

Example: range [3, 10], length=8
  - Take range starting at 3, length 8  → covers [3, 10]
  - For non-power-of-2 length, use two overlapping ranges of
    length 2^j where j = log2(length)
  - e.g., range [3, 9], length=7 → j=2 (length 4)
    - [3, 6] and [6, 9]  ← overlapping at index 6
    - min([3,9]) = min(min[3,6], min[6,9])

ALGORITHM
---------
1. Precompute table[i][j] = min of A[i..i+2^j-1]
   - Size: N rows x log2(N)+1 cols
   - Recurrence: table[i][j] = min(table[i][j-1], table[i+2^(j-1)][j-1])

2. Query(L, R):
   - k = floor(log2(R - L + 1))
   - return min(table[L][k], table[R - 2^k + 1][k])

COMPLEXITY
----------
- Build: O(N log N) time + space
- Query: O(1) per query

============================================================
"""

import math


# ============================================================
# Sparse Table for RANGE MINIMUM
# ============================================================
class SparseTableMin:
    def __init__(self, arr):
        self.n = len(arr)
        self.k = max(1, int(math.log2(self.n)) + 1)
        # table[i][j] = min of arr[i .. i + 2^j - 1]
        self.table = [[0] * self.k for _ in range(self.n)]
        self.log = [0] * (self.n + 1)
        self._build_log()
        self._build(arr)

    def _build_log(self):
        """Precompute log2 values for O(1) lookup."""
        for i in range(2, self.n + 1):
            self.log[i] = self.log[i // 2] + 1

    def _build(self, arr):
        # j = 0: ranges of length 1
        for i in range(self.n):
            self.table[i][0] = arr[i]

        # j > 0: combine two halves
        j = 1
        while (1 << j) <= self.n:
            i = 0
            while i + (1 << j) <= self.n:
                self.table[i][j] = min(
                    self.table[i][j - 1],
                    self.table[i + (1 << (j - 1))][j - 1]
                )
                i += 1
            j += 1

    def query(self, L, R):
        """Min of arr[L..R] inclusive — O(1)."""
        length = R - L + 1
        k = self.log[length]
        return min(
            self.table[L][k],
            self.table[R - (1 << k) + 1][k]
        )


# ============================================================
# Generic Sparse Table (any idempotent operation)
# ============================================================
class SparseTable:
    """Generic — pass any idempotent function (min, max, gcd, &, |)."""

    def __init__(self, arr, func=min):
        self.func = func
        self.n = len(arr)
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
        k = self.log[R - L + 1]
        return self.func(
            self.table[L][k],
            self.table[R - (1 << k) + 1][k]
        )


# ============================================================
# Sparse Table for SUM (uses disjoint ranges — slower queries O(log N))
# ============================================================
class SparseTableSum:
    """For non-idempotent ops like sum, must use DISJOINT ranges → O(log N) query.
    For sum, prefer prefix sum or Fenwick tree."""

    def __init__(self, arr):
        self.n = len(arr)
        self.k = max(1, int(math.log2(self.n)) + 1)
        self.table = [[0] * self.k for _ in range(self.n)]
        for i in range(self.n):
            self.table[i][0] = arr[i]
        j = 1
        while (1 << j) <= self.n:
            i = 0
            while i + (1 << j) <= self.n:
                self.table[i][j] = (
                    self.table[i][j - 1] +
                    self.table[i + (1 << (j - 1))][j - 1]
                )
                i += 1
            j += 1

    def query(self, L, R):
        result = 0
        j = int(math.log2(R - L + 1))
        while L <= R:
            while L + (1 << j) - 1 > R:
                j -= 1
            result += self.table[L][j]
            L += (1 << j)
        return result


# ============================================================
# Demo / Tests
# ============================================================
if __name__ == "__main__":
    arr = [7, 2, 3, 0, 5, 10, 3, 12, 18]

    print("Array:", arr)
    print("Indices:", list(range(len(arr))))

    st_min = SparseTableMin(arr)
    print("\n--- RANGE MIN QUERIES ---")
    print(f"min(0, 4) = {st_min.query(0, 4)}  (expected 0)")
    print(f"min(3, 6) = {st_min.query(3, 6)}  (expected 0)")
    print(f"min(5, 8) = {st_min.query(5, 8)}  (expected 3)")
    print(f"min(7, 8) = {st_min.query(7, 8)}  (expected 12)")

    st_max = SparseTable(arr, max)
    print("\n--- RANGE MAX QUERIES ---")
    print(f"max(0, 4) = {st_max.query(0, 4)}  (expected 7)")
    print(f"max(2, 7) = {st_max.query(2, 7)}  (expected 12)")

    from math import gcd
    st_gcd = SparseTable([12, 18, 24, 36, 48, 60], gcd)
    print("\n--- RANGE GCD QUERIES ---")
    print(f"gcd(0, 2) = {st_gcd.query(0, 2)}  (gcd of 12,18,24)")
    print(f"gcd(2, 5) = {st_gcd.query(2, 5)}  (gcd of 24,36,48,60)")

    st_sum = SparseTableSum([1, 2, 3, 4, 5, 6, 7, 8])
    print("\n--- RANGE SUM (disjoint, O(log N)) ---")
    print(f"sum(0, 7) = {st_sum.query(0, 7)}  (expected 36)")
    print(f"sum(2, 5) = {st_sum.query(2, 5)}  (expected 18)")

    print("\n" + "=" * 60)
    print("INTERVIEW Q&A")
    print("=" * 60)
    print("""
Q: Sparse Table vs Segment Tree — kab kya?
A: Sparse Table — immutable arr + idempotent (min/max/gcd) → O(1) query.
   Segment Tree — supports updates, any operation → O(log N) query.

Q: Sparse Table sum ke liye kyu nahi?
A: Sum non-idempotent — overlap mein double-count. Use prefix sum/Fenwick.

Q: log2(N) precompute kyu?
A: Math.log2 floating-point slow + inaccurate. Lookup O(1).

Q: Real-world use?
A: Competitive programming, static analysis tools, immutable data range queries.
   Genomics: range min on read quality scores.
   Time-series: range max temperature over fixed historical window.
""")
