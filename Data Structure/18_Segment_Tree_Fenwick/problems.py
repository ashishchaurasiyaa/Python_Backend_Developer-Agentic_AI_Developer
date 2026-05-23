"""18 — Segment Tree & Fenwick Tree — Problems | 10 problems | Medium→Hard"""
from typing import List
import math
from sortedcontainers import SortedList

# ── Reusable Data Structures ────────────────────────────────

class FenwickTree:
    def __init__(self, n):
        self.n = n; self.tree = [0] * (n + 1)
    def update(self, i, delta):
        while i <= self.n: self.tree[i] += delta; i += i & (-i)
    def prefix_sum(self, i):
        s = 0
        while i > 0: s += self.tree[i]; i -= i & (-i)
        return s
    def range_sum(self, l, r): return self.prefix_sum(r) - self.prefix_sum(l-1)

class SegTree:
    def __init__(self, n):
        self.n = n; self.tree = [0] * (4*n)
    def update(self, i, delta, node=0, lo=0, hi=-1):
        if hi == -1: hi = self.n - 1
        if lo == hi: self.tree[node] += delta; return
        mid = (lo+hi)//2
        if i <= mid: self.update(i, delta, 2*node+1, lo, mid)
        else: self.update(i, delta, 2*node+2, mid+1, hi)
        self.tree[node] = self.tree[2*node+1] + self.tree[2*node+2]
    def query(self, l, r, node=0, lo=0, hi=-1):
        if hi == -1: hi = self.n - 1
        if r < lo or hi < l: return 0
        if l <= lo and hi <= r: return self.tree[node]
        mid = (lo+hi)//2
        return self.query(l, r, 2*node+1, lo, mid) + self.query(l, r, 2*node+2, mid+1, hi)


# ─────────────────────────────────────────────
# P01. Range Sum Query - Mutable  [Medium][LC 307]
# ─────────────────────────────────────────────
"""
Implement NumArray with update(i, val) and sumRange(l, r) both O(log n).
"""
class NumArray:
    def __init__(self, nums: List[int]):
        self.n = len(nums)
        self.ft = FenwickTree(self.n)
        self.nums = [0] * self.n
        for i, v in enumerate(nums):
            self.update(i, v)

    def update(self, index: int, val: int) -> None:
        delta = val - self.nums[index]
        self.nums[index] = val
        self.ft.update(index + 1, delta)   # 1-indexed

    def sumRange(self, left: int, right: int) -> int:
        return self.ft.range_sum(left + 1, right + 1)

na = NumArray([1, 3, 5])
print("P01:", na.sumRange(0, 2))  # 9
na.update(1, 2)
print("P01:", na.sumRange(0, 2))  # 8


# ─────────────────────────────────────────────
# P02. Count of Smaller Numbers After Self  [Hard][LC 315]
# ─────────────────────────────────────────────
"""
For each nums[i], count numbers to its right that are smaller.
Input: [5,2,6,1]  Output: [2,1,1,0]
Strategy: process right to left, Fenwick on coordinate-compressed values.
"""
def countSmaller(nums: List[int]) -> List[int]:
    # Coordinate compression
    sorted_unique = sorted(set(nums))
    rank = {v: i+1 for i, v in enumerate(sorted_unique)}  # 1-indexed
    ft = FenwickTree(len(sorted_unique))
    result = []
    for n in reversed(nums):
        r = rank[n]
        result.append(ft.prefix_sum(r - 1))  # count elements with rank < r
        ft.update(r, 1)
    return result[::-1]

print("P02:", countSmaller([5, 2, 6, 1]))  # [2,1,1,0]
print("P02:", countSmaller([2, 0, 1]))     # [2,1,0]


# ─────────────────────────────────────────────
# P03. Range Sum Query 2D - Mutable  [Hard][LC 308]
# ─────────────────────────────────────────────
"""
2D matrix with update and sumRegion queries.
"""
class NumMatrix:
    def __init__(self, matrix: List[List[int]]):
        self.m, self.n = len(matrix), len(matrix[0])
        self.matrix = [[0]*self.n for _ in range(self.m)]
        self.tree = [[0]*(self.n+1) for _ in range(self.m+1)]
        for r in range(self.m):
            for c in range(self.n):
                self.update(r, c, matrix[r][c])

    def _update_tree(self, r, c, delta):
        i = r + 1
        while i <= self.m:
            j = c + 1
            while j <= self.n:
                self.tree[i][j] += delta
                j += j & (-j)
            i += i & (-i)

    def _prefix(self, r, c):
        s = 0; i = r + 1
        while i > 0:
            j = c + 1
            while j > 0: s += self.tree[i][j]; j -= j & (-j)
            i -= i & (-i)
        return s

    def update(self, row, col, val):
        delta = val - self.matrix[row][col]
        self.matrix[row][col] = val
        self._update_tree(row, col, delta)

    def sumRegion(self, r1, c1, r2, c2):
        return (self._prefix(r2, c2) - self._prefix(r1-1, c2)
              - self._prefix(r2, c1-1) + self._prefix(r1-1, c1-1))

nm = NumMatrix([[3,0,1,4,2],[5,6,3,2,1],[1,2,0,1,5],[4,1,0,1,7],[1,0,3,0,5]])
print("P03:", nm.sumRegion(2,1,4,3))  # 8
nm.update(3,2,2)
print("P03:", nm.sumRegion(2,1,4,3))  # 10


# ─────────────────────────────────────────────
# P04. My Calendar I  [Medium][LC 729]
# ─────────────────────────────────────────────
"""
Book events [start,end). Return False if double booking.
Use sorted list + binary search.
"""
class MyCalendar:
    def __init__(self):
        self.calendar = SortedList(key=lambda x: x[0])

    def book(self, start: int, end: int) -> bool:
        idx = self.calendar.bisect_left((start, end))
        # Check overlap with previous interval
        if idx > 0:
            ps, pe = self.calendar[idx-1]
            if ps < end and start < pe: return False
        # Check overlap with next interval
        if idx < len(self.calendar):
            ns, ne = self.calendar[idx]
            if start < ne and ns < end: return False
        self.calendar.add((start, end))
        return True

mc = MyCalendar()
print("P04:", mc.book(10, 20))  # True
print("P04:", mc.book(15, 25))  # False
print("P04:", mc.book(20, 30))  # True


# ─────────────────────────────────────────────
# P05. My Calendar III  [Hard][LC 732]
# ─────────────────────────────────────────────
"""
Return maximum k-booking (max simultaneous events) after each book().
Use sweep line with sorted dict (difference array).
"""
from sortedcontainers import SortedDict

class MyCalendarThree:
    def __init__(self):
        self.diff = SortedDict()

    def book(self, start: int, end: int) -> int:
        self.diff[start] = self.diff.get(start, 0) + 1
        self.diff[end]   = self.diff.get(end,   0) - 1
        max_k = curr = 0
        for v in self.diff.values():
            curr += v
            max_k = max(max_k, curr)
        return max_k

mc3 = MyCalendarThree()
for s, e in [(10,20),(50,60),(10,40),(5,15),(5,10),(25,55)]:
    print("P05:", mc3.book(s, e))  # 1,1,2,3,3,3


# ─────────────────────────────────────────────
# P06. The Skyline Problem  [Hard][LC 218]
# ─────────────────────────────────────────────
"""
Buildings = [left, right, height]. Return skyline outline.
Strategy: events at each x with +height (enter) and -height (exit).
Use max-heap (sorted structure) to track current max height.
"""
import heapq

def getSkyline(buildings: List[List[int]]) -> List[List[int]]:
    events = []
    for l, r, h in buildings:
        events.append((l, -h, r))   # enter: negative height for max-heap
        events.append((r, 0, 0))    # exit

    events.sort()
    result = []
    # heap: (-height, end_x) — active buildings
    heap = [(0, float('inf'))]  # ground level, never expires

    for x, neg_h, end in events:
        # Remove expired buildings
        while heap[0][1] <= x:
            heapq.heappop(heap)
        if neg_h != 0:
            heapq.heappush(heap, (neg_h, end))
        cur_height = -heap[0][0]
        if not result or result[-1][1] != cur_height:
            result.append([x, cur_height])

    return result

print("P06:", getSkyline([[2,9,10],[3,7,15],[5,12,12],[15,20,10],[19,24,8]]))


# ─────────────────────────────────────────────
# P07. Falling Squares  [Hard][LC 699]
# ─────────────────────────────────────────────
"""
Squares fall on x-axis. After each drop, return max height.
Strategy: coordinate compress x-coords, segment tree with lazy for range max.
Simplified: O(n²) with SortedList for this version.
"""
def fallingSquares(positions: List[List[int]]) -> List[int]:
    intervals = []   # [(left, right, height)]
    result = []
    max_height = 0

    for left, size in positions:
        right = left + size
        # Height of this square = max height of any interval overlapping [left, right) + size
        base = 0
        for l, r, h in intervals:
            if l < right and left < r:   # overlap
                base = max(base, h)
        height = base + size
        intervals.append((left, right, height))
        max_height = max(max_height, height)
        result.append(max_height)

    return result

print("P07:", fallingSquares([[1,2],[2,3],[6,1]]))  # [2,5,5]
print("P07:", fallingSquares([[100,100],[200,100]]))  # [100,100]


# ─────────────────────────────────────────────
# P08. Number of Longest Increasing Subsequence  [Medium][LC 673]
# ─────────────────────────────────────────────
"""
Count number of LIS (not just length).
DP: length[i] = LIS ending at i, count[i] = how many such LIS.
"""
def findNumberOfLIS(nums: List[int]) -> int:
    n = len(nums)
    if n == 0: return 0
    length = [1] * n   # LIS length ending at i
    count  = [1] * n   # number of LIS of that length ending at i

    for i in range(1, n):
        for j in range(i):
            if nums[j] < nums[i]:
                if length[j] + 1 > length[i]:
                    length[i] = length[j] + 1
                    count[i]  = count[j]
                elif length[j] + 1 == length[i]:
                    count[i] += count[j]

    max_len = max(length)
    return sum(c for l, c in zip(length, count) if l == max_len)

print("P08:", findNumberOfLIS([1,3,5,4,7]))  # 2 ([1,3,5,7] and [1,3,4,7])
print("P08:", findNumberOfLIS([2,2,2,2,2]))  # 5


# ─────────────────────────────────────────────
# P09. Count of Range Sum  [Hard][LC 327]
# ─────────────────────────────────────────────
"""
Count subarrays with sum in [lower, upper].
Strategy: prefix sums + merge sort (count inversions style).
"""
def countRangeSum(nums: List[int], lower: int, upper: int) -> int:
    prefix = [0]
    for n in nums:
        prefix.append(prefix[-1] + n)

    def merge_count(sums):
        if len(sums) <= 1: return 0
        mid = len(sums) // 2
        left, right = sums[:mid], sums[mid:]
        count = merge_count(left) + merge_count(right)
        j = k = 0
        for l in left:
            while j < len(right) and right[j] - l < lower: j += 1
            while k < len(right) and right[k] - l <= upper: k += 1
            count += k - j
        sums[:] = sorted(left + right)
        return count

    return merge_count(prefix)

print("P09:", countRangeSum([-2,5,-1], -2, 2))  # 3


# ─────────────────────────────────────────────
# P10. Maximum Sum of Two Non-Overlapping Subarrays  [Medium][LC 1031]
# ─────────────────────────────────────────────
"""
Find max sum of two non-overlapping subarrays of lengths L and M.
Strategy: prefix sums + sliding windows.
"""
def maxSumTwoNoOverlap(nums: List[int], firstLen: int, secondLen: int) -> int:
    n = len(nums)
    prefix = [0] * (n + 1)
    for i in range(n):
        prefix[i+1] = prefix[i] + nums[i]

    def solve(L, M):
        # max of (best L-window ending before M-window starts)
        result = max_l = 0
        for i in range(L + M, n + 1):
            max_l = max(max_l, prefix[i-M] - prefix[i-M-L])
            result = max(result, max_l + prefix[i] - prefix[i-M])
        return result

    return max(solve(firstLen, secondLen), solve(secondLen, firstLen))

print("P10:", maxSumTwoNoOverlap([0,6,5,2,2,5,1,9,4], 1, 2))  # 20
print("P10:", maxSumTwoNoOverlap([3,8,1,3,2,1,8,9,0], 3, 2))  # 29


"""
COMPLEXITY SUMMARY:
─────────────────────────────────────────────────────────────────────
Range Sum Mutable      O(log n) update+query   Fenwick Tree
Count Smaller After    O(n log n)              Fenwick + coord compress
2D Range Sum Mutable   O(log m log n)          2D Fenwick Tree
My Calendar I          O(n log n) per book     SortedList + binary search
My Calendar III        O(n) per book           Sorted difference array
Skyline Problem        O(n log n)              Events + max-heap
Falling Squares        O(n²)                   naive; O(n log n) with lazy seg tree
Number of LIS          O(n²) DP                O(n log n) possible with BIT
Count Range Sum        O(n log n)              Merge sort on prefix sums
Max Two Non-Overlap    O(n)                    Prefix sum + two passes
"""
