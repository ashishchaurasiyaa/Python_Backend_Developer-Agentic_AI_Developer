"""
╔══════════════════════════════════════════════════════════════════╗
║           BINARY SEARCH — 12 LeetCode-Style Problems             ║
╚══════════════════════════════════════════════════════════════════╝
"""

from typing import List
import bisect

# ══════════════════════════════════════════════════════════════════
# Problem 1: Binary Search (LC 704)
# ══════════════════════════════════════════════════════════════════
def search(nums: List[int], target: int) -> int:
    """
    Given a sorted array of distinct integers, return the index of
    target, or -1 if not found.

    Example:
      nums=[-1,0,3,5,9,12], target=9 → 4
      nums=[-1,0,3,5,9,12], target=2 → -1
    """
    lo, hi = 0, len(nums) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if nums[mid] == target:
            return mid
        elif nums[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1

print("=== Binary Search ===")
print(search([-1,0,3,5,9,12], 9))  # 4
print(search([-1,0,3,5,9,12], 2))  # -1
# Time: O(log n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 2: Search a 2D Matrix (LC 74)
# ══════════════════════════════════════════════════════════════════
def searchMatrix(matrix: List[List[int]], target: int) -> bool:
    """
    Integers in each row sorted left→right. First int of each row
    is greater than last int of previous row. Find target.

    Approach: Treat the matrix as a flat sorted array.
    Index i maps to matrix[i // n][i % n].

    Example:
      matrix=[[1,3,5,7],[10,11,16,20],[23,30,34,60]], target=3 → True
      matrix=[[1,3,5,7],[10,11,16,20],[23,30,34,60]], target=13 → False
    """
    m, n = len(matrix), len(matrix[0])
    lo, hi = 0, m * n - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        val = matrix[mid // n][mid % n]
        if val == target:
            return True
        elif val < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return False

print("\n=== Search a 2D Matrix ===")
matrix = [[1,3,5,7],[10,11,16,20],[23,30,34,60]]
print(searchMatrix(matrix, 3))   # True
print(searchMatrix(matrix, 13))  # False
# Time: O(log(m*n)) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 3: Koko Eating Bananas (LC 875) — Binary Search on Answer
# ══════════════════════════════════════════════════════════════════
def minEatingSpeed(piles: List[int], h: int) -> int:
    """
    Koko has piles of bananas. Guards return in h hours. She wants
    to eat at minimum speed k (bananas/hour). Find minimum k.
    She eats from one pile per hour (can't switch mid-pile).

    Approach: Binary search on answer k in [1, max(piles)].
    can_finish(k): sum(ceil(p/k)) <= h

    Example:
      piles=[3,6,7,11], h=8 → 4
      piles=[30,11,23,4,20], h=5 → 30
    """
    def can_finish(speed):
        return sum((p + speed - 1) // speed for p in piles) <= h

    lo, hi = 1, max(piles)
    while lo < hi:
        mid = (lo + hi) // 2
        if can_finish(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo

print("\n=== Koko Eating Bananas ===")
print(minEatingSpeed([3,6,7,11], 8))      # 4
print(minEatingSpeed([30,11,23,4,20], 5)) # 30
# Time: O(n log(max_pile)) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 4: Find Minimum in Rotated Sorted Array (LC 153)
# ══════════════════════════════════════════════════════════════════
def findMin(nums: List[int]) -> int:
    """
    Find the minimum element in a rotated sorted array (no duplicates).

    Approach: If nums[mid] > nums[hi], min is in right half.
    Otherwise, min is in left half (including mid).

    Example:
      [3,4,5,1,2] → 1
      [4,5,6,7,0,1,2] → 0
      [11,13,15,17] → 11
    """
    lo, hi = 0, len(nums) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if nums[mid] > nums[hi]:
            lo = mid + 1
        else:
            hi = mid
    return nums[lo]

print("\n=== Find Minimum in Rotated Sorted Array ===")
print(findMin([3,4,5,1,2]))      # 1
print(findMin([4,5,6,7,0,1,2]))  # 0
print(findMin([11,13,15,17]))    # 11
# Time: O(log n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 5: Search in Rotated Sorted Array (LC 33)
# ══════════════════════════════════════════════════════════════════
def searchRotated(nums: List[int], target: int) -> int:
    """
    Search in a rotated sorted array (no duplicates). Return index or -1.

    Approach: One of the two halves is always sorted.
    Check which half is sorted, then check if target is in it.

    Example:
      nums=[4,5,6,7,0,1,2], target=0 → 4
      nums=[4,5,6,7,0,1,2], target=3 → -1
    """
    lo, hi = 0, len(nums) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if nums[mid] == target:
            return mid
        if nums[lo] <= nums[mid]:   # left half is sorted
            if nums[lo] <= target < nums[mid]:
                hi = mid - 1
            else:
                lo = mid + 1
        else:                       # right half is sorted
            if nums[mid] < target <= nums[hi]:
                lo = mid + 1
            else:
                hi = mid - 1
    return -1

print("\n=== Search in Rotated Sorted Array ===")
print(searchRotated([4,5,6,7,0,1,2], 0))  # 4
print(searchRotated([4,5,6,7,0,1,2], 3))  # -1
print(searchRotated([1], 0))              # -1
# Time: O(log n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 6: Time Based Key-Value Store (LC 981)
# ══════════════════════════════════════════════════════════════════
class TimeMap:
    """
    Design a time-based key-value data structure:
    - set(key, value, timestamp): stores the value at that timestamp
    - get(key, timestamp): returns value with largest timestamp <= given timestamp

    Approach: dict maps key → list of (timestamp, value) in sorted order.
    Binary search (bisect_right) to find the right timestamp.

    Example:
      set("foo","bar",1), get("foo",1) → "bar"
      get("foo",3) → "bar"
      set("foo","bar2",4), get("foo",4) → "bar2", get("foo",5) → "bar2"
    """
    def __init__(self):
        self.store = {}  # key → [(timestamp, value)]

    def set(self, key: str, value: str, timestamp: int) -> None:
        if key not in self.store:
            self.store[key] = []
        self.store[key].append((timestamp, value))

    def get(self, key: str, timestamp: int) -> str:
        if key not in self.store:
            return ""
        entries = self.store[key]
        # Find rightmost entry with timestamp <= given timestamp
        lo, hi = 0, len(entries) - 1
        result = ""
        while lo <= hi:
            mid = (lo + hi) // 2
            if entries[mid][0] <= timestamp:
                result = entries[mid][1]
                lo = mid + 1
            else:
                hi = mid - 1
        return result

print("\n=== Time Based Key-Value Store ===")
tm = TimeMap()
tm.set("foo", "bar", 1)
print(tm.get("foo", 1))   # bar
print(tm.get("foo", 3))   # bar
tm.set("foo", "bar2", 4)
print(tm.get("foo", 4))   # bar2
print(tm.get("foo", 5))   # bar2
# Time: O(log n) get, O(1) set | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 7: Median of Two Sorted Arrays (LC 4)
# ══════════════════════════════════════════════════════════════════
def findMedianSortedArrays(nums1: List[int], nums2: List[int]) -> float:
    """
    Find the median of two sorted arrays in O(log(min(m,n))).

    Approach: Binary search on partition of smaller array.
    We want to split both arrays so left halves have total n//2 elements
    and max(left) <= min(right).

    Example:
      nums1=[1,3], nums2=[2] → 2.0
      nums1=[1,2], nums2=[3,4] → 2.5
    """
    A, B = nums1, nums2
    if len(A) > len(B):
        A, B = B, A
    m, n = len(A), len(B)
    half = (m + n) // 2

    lo, hi = 0, m
    while lo <= hi:
        i = (lo + hi) // 2   # partition index in A
        j = half - i         # partition index in B

        A_left  = A[i-1] if i > 0 else float('-inf')
        A_right = A[i]   if i < m else float('inf')
        B_left  = B[j-1] if j > 0 else float('-inf')
        B_right = B[j]   if j < n else float('inf')

        if A_left <= B_right and B_left <= A_right:
            if (m + n) % 2 == 1:
                return float(min(A_right, B_right))
            return (max(A_left, B_left) + min(A_right, B_right)) / 2
        elif A_left > B_right:
            hi = i - 1
        else:
            lo = i + 1
    return 0.0

print("\n=== Median of Two Sorted Arrays ===")
print(findMedianSortedArrays([1,3], [2]))      # 2.0
print(findMedianSortedArrays([1,2], [3,4]))    # 2.5
print(findMedianSortedArrays([0,0], [0,0]))    # 0.0
# Time: O(log(min(m,n))) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 8: Find Peak Element (LC 162)
# ══════════════════════════════════════════════════════════════════
def findPeakElement(nums: List[int]) -> int:
    """
    A peak element is greater than its neighbors. Return any peak index.
    nums[-1] = nums[n] = -infinity (boundary condition).

    Approach: Binary search. If nums[mid] < nums[mid+1], peak is to the right.
    Otherwise, peak is to the left (including mid).

    Example:
      [1,2,3,1] → 2
      [1,2,1,3,5,6,4] → 1 or 5
    """
    lo, hi = 0, len(nums) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if nums[mid] < nums[mid + 1]:
            lo = mid + 1   # peak is on the right
        else:
            hi = mid       # peak is on the left (or mid itself)
    return lo

print("\n=== Find Peak Element ===")
print(findPeakElement([1,2,3,1]))        # 2
print(findPeakElement([1,2,1,3,5,6,4])) # 5 (or 1)
# Time: O(log n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 9: Find First and Last Position (LC 34)
# ══════════════════════════════════════════════════════════════════
def searchRange(nums: List[int], target: int) -> List[int]:
    """
    Given a sorted array, find the starting and ending position of target.
    Return [-1, -1] if not found.

    Approach: Two binary searches — one for leftmost, one for rightmost.

    Example:
      nums=[5,7,7,8,8,10], target=8 → [3,4]
      nums=[5,7,7,8,8,10], target=6 → [-1,-1]
    """
    def find_left(target):
        lo, hi = 0, len(nums)
        while lo < hi:
            mid = (lo + hi) // 2
            if nums[mid] < target:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def find_right(target):
        lo, hi = 0, len(nums)
        while lo < hi:
            mid = (lo + hi) // 2
            if nums[mid] <= target:
                lo = mid + 1
            else:
                hi = mid
        return lo - 1

    left = find_left(target)
    if left == len(nums) or nums[left] != target:
        return [-1, -1]
    return [left, find_right(target)]

print("\n=== Find First and Last Position ===")
print(searchRange([5,7,7,8,8,10], 8))  # [3, 4]
print(searchRange([5,7,7,8,8,10], 6))  # [-1, -1]
print(searchRange([], 0))              # [-1, -1]
# Time: O(log n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 10: Capacity to Ship Packages (LC 1011)
# ══════════════════════════════════════════════════════════════════
def shipWithinDays(weights: List[int], days: int) -> int:
    """
    Ship all packages within 'days' days. Packages must be loaded in order.
    Find minimum weight capacity of the ship.

    Approach: Binary search on answer in [max(weights), sum(weights)].
    can_ship(cap): simulate and count days needed.

    Example:
      weights=[1,2,3,4,5,6,7,8,9,10], days=5 → 15
      weights=[3,2,2,4,1,4], days=3 → 6
    """
    def can_ship(capacity):
        days_needed = 1
        current_load = 0
        for w in weights:
            if current_load + w > capacity:
                days_needed += 1
                current_load = 0
            current_load += w
        return days_needed <= days

    lo, hi = max(weights), sum(weights)
    while lo < hi:
        mid = (lo + hi) // 2
        if can_ship(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo

print("\n=== Capacity to Ship Packages ===")
print(shipWithinDays([1,2,3,4,5,6,7,8,9,10], 5))  # 15
print(shipWithinDays([3,2,2,4,1,4], 3))             # 6
print(shipWithinDays([1,2,3,1,1], 4))               # 3
# Time: O(n log(sum)) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 11: Split Array Largest Sum (LC 410)
# ══════════════════════════════════════════════════════════════════
def splitArray(nums: List[int], k: int) -> int:
    """
    Split nums into k non-empty subarrays to minimize the largest sum.

    Approach: Binary search on answer in [max(nums), sum(nums)].
    can_split(mid): can we split into <= k subarrays each with sum <= mid?

    Example:
      nums=[7,2,5,10,8], k=2 → 18
      nums=[1,2,3,4,5], k=2 → 9
    """
    def can_split(max_sum):
        count = 1
        current = 0
        for num in nums:
            if current + num > max_sum:
                count += 1
                current = 0
            current += num
        return count <= k

    lo, hi = max(nums), sum(nums)
    while lo < hi:
        mid = (lo + hi) // 2
        if can_split(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo

print("\n=== Split Array Largest Sum ===")
print(splitArray([7,2,5,10,8], 2))  # 18
print(splitArray([1,2,3,4,5], 2))   # 9
# Time: O(n log(sum)) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 12: Search in Rotated Sorted Array II (LC 81)
# ══════════════════════════════════════════════════════════════════
def searchRotatedII(nums: List[int], target: int) -> bool:
    """
    Search in a rotated sorted array that MAY CONTAIN DUPLICATES.
    Return True if target exists.

    Difference from LC 33: When nums[lo] == nums[mid] == nums[hi],
    we can't determine which half is sorted. Skip duplicates.

    Example:
      [2,5,6,0,0,1,2], target=0 → True
      [2,5,6,0,0,1,2], target=3 → False
    """
    lo, hi = 0, len(nums) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if nums[mid] == target:
            return True
        # Can't determine sorted half — skip duplicates
        if nums[lo] == nums[mid] == nums[hi]:
            lo += 1
            hi -= 1
        elif nums[lo] <= nums[mid]:  # left half sorted
            if nums[lo] <= target < nums[mid]:
                hi = mid - 1
            else:
                lo = mid + 1
        else:                        # right half sorted
            if nums[mid] < target <= nums[hi]:
                lo = mid + 1
            else:
                hi = mid - 1
    return False

print("\n=== Search in Rotated Sorted Array II ===")
print(searchRotatedII([2,5,6,0,0,1,2], 0))  # True
print(searchRotatedII([2,5,6,0,0,1,2], 3))  # False
# Time: O(log n) avg, O(n) worst | Space: O(1)

print("\n✓ All 12 Binary Search problems solved!")
