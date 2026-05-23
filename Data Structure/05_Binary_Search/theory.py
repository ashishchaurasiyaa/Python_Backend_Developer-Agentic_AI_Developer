"""
╔══════════════════════════════════════════════════════════════════╗
║              BINARY SEARCH — Complete Theory Guide               ║
╚══════════════════════════════════════════════════════════════════╝

WHAT IS BINARY SEARCH?
───────────────────────
Binary Search is a search algorithm that finds a target in a SORTED
collection by repeatedly halving the search space.

Core idea: Compare target with middle element.
  - If equal   → found!
  - If target < mid → search LEFT half
  - If target > mid → search RIGHT half

WHY O(log n)?
─────────────
Each comparison eliminates HALF the remaining elements.
  n → n/2 → n/4 → ... → 1
  After k steps: n / 2^k = 1 → k = log₂(n)

COMPLEXITY TABLE
─────────────────────────────────────────────────────────────────
Algorithm        Best     Average    Worst    Space
─────────────────────────────────────────────────────────────────
Linear Search    O(1)     O(n)       O(n)     O(1)
Binary Search    O(1)     O(log n)   O(log n) O(1) iterative
                                              O(log n) recursive
─────────────────────────────────────────────────────────────────

WHEN TO USE BINARY SEARCH?
───────────────────────────
1. Array is sorted (or answer space is monotonic)
2. "Find minimum/maximum satisfying condition" → binary search on ANSWER
3. O(log n) search needed
4. Rotated sorted arrays (still binary searchable with modifications)

THE THREE TEMPLATES
────────────────────
"""

from typing import List
import bisect

# ─────────────────────────────────────────────
# TEMPLATE 1: Standard Binary Search
# Find exact target. Returns index or -1.
# ─────────────────────────────────────────────
print("=" * 60)
print("TEMPLATE 1: Standard Binary Search")
print("=" * 60)

def binary_search(nums: List[int], target: int) -> int:
    """
    Finds the index of target in sorted nums.
    Returns -1 if not found.
    Loop invariant: target is in nums[lo..hi] if it exists.
    """
    lo, hi = 0, len(nums) - 1
    while lo <= hi:
        mid = lo + (hi - lo) // 2   # avoid overflow (not an issue in Python but good habit)
        if nums[mid] == target:
            return mid
        elif nums[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1

nums = [1, 3, 5, 7, 9, 11, 13]
print(f"Search 7 in {nums}: index {binary_search(nums, 7)}")    # 3
print(f"Search 6 in {nums}: index {binary_search(nums, 6)}")    # -1

# ─────────────────────────────────────────────
# TEMPLATE 2: Left-Most (Lower Bound)
# Find first position where nums[i] >= target
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("TEMPLATE 2: Left-Most Position (Lower Bound)")
print("=" * 60)

def lower_bound(nums: List[int], target: int) -> int:
    """
    Returns the leftmost index where nums[i] >= target.
    If all elements < target, returns len(nums).

    This is equivalent to bisect.bisect_left(nums, target).

    Key: hi = len(nums) (not len-1), loop until lo == hi.
    """
    lo, hi = 0, len(nums)
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if nums[mid] < target:
            lo = mid + 1
        else:
            hi = mid   # include mid as possible answer
    return lo

nums = [1, 2, 2, 2, 3, 4, 5]
print(f"Lower bound of 2 in {nums}: {lower_bound(nums, 2)}")    # 1
print(f"Lower bound of 3 in {nums}: {lower_bound(nums, 3)}")    # 4
print(f"bisect_left: {bisect.bisect_left(nums, 2)}")            # 1 (same)

# ─────────────────────────────────────────────
# TEMPLATE 3: Right-Most (Upper Bound)
# Find last position where nums[i] <= target
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("TEMPLATE 3: Right-Most Position (Upper Bound)")
print("=" * 60)

def upper_bound(nums: List[int], target: int) -> int:
    """
    Returns the first index where nums[i] > target.
    (i.e., one past the last occurrence of target)

    This is equivalent to bisect.bisect_right(nums, target).
    """
    lo, hi = 0, len(nums)
    while lo < hi:
        mid = lo + (hi - lo) // 2
        if nums[mid] <= target:
            lo = mid + 1
        else:
            hi = mid
    return lo

nums = [1, 2, 2, 2, 3, 4, 5]
print(f"Upper bound of 2 in {nums}: {upper_bound(nums, 2)}")    # 4
print(f"bisect_right: {bisect.bisect_right(nums, 2)}")          # 4 (same)

# First and last position of target
def first_last(nums, target):
    left = bisect.bisect_left(nums, target)
    if left == len(nums) or nums[left] != target:
        return [-1, -1]
    right = bisect.bisect_right(nums, target) - 1
    return [left, right]

print(f"First/last of 2 in {nums}: {first_last(nums, 2)}")  # [1, 3]

# ─────────────────────────────────────────────
# Python's bisect module
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("PYTHON bisect MODULE")
print("=" * 60)

bisect_guide = """
bisect.bisect_left(a, x)   → leftmost position to insert x (first x)
bisect.bisect_right(a, x)  → rightmost position to insert x (after last x)
bisect.insort_left(a, x)   → insert x maintaining sorted order (left)
bisect.insort_right(a, x)  → insert x maintaining sorted order (right)

# Example use cases:
a = [1, 3, 5, 7, 9]
bisect.bisect_left(a, 5)   → 2  (index of 5)
bisect.bisect_left(a, 4)   → 2  (where 4 would go)
bisect.bisect_right(a, 5)  → 3  (after 5)
"""
print(bisect_guide)

# ─────────────────────────────────────────────
# PATTERN 1: Binary Search on Rotated Array
# ─────────────────────────────────────────────
print("=" * 60)
print("PATTERN 1: Search in Rotated Sorted Array")
print("=" * 60)

"""
Key insight: In a rotated array, ONE of the two halves is always sorted.
Determine which half is sorted, then check if target is in that half.
"""

def search_rotated(nums: List[int], target: int) -> int:
    lo, hi = 0, len(nums) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if nums[mid] == target:
            return mid
        # Left half is sorted
        if nums[lo] <= nums[mid]:
            if nums[lo] <= target < nums[mid]:
                hi = mid - 1
            else:
                lo = mid + 1
        # Right half is sorted
        else:
            if nums[mid] < target <= nums[hi]:
                lo = mid + 1
            else:
                hi = mid - 1
    return -1

print(search_rotated([4,5,6,7,0,1,2], 0))  # 4
print(search_rotated([4,5,6,7,0,1,2], 3))  # -1

# ─────────────────────────────────────────────
# PATTERN 2: Binary Search on Answer
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("PATTERN 2: Binary Search on Answer")
print("=" * 60)

"""
When the answer lies in a range [lo, hi] and there's a monotonic
condition (feasible/not feasible), binary search on the answer itself.

Template:
  def can_do(mid) → bool: ...

  lo, hi = min_possible, max_possible
  while lo < hi:
      mid = (lo + hi) // 2
      if can_do(mid):
          hi = mid        # try smaller (find minimum)
      else:
          lo = mid + 1
  return lo

Example: Koko eating bananas at speed k — can she finish in h hours?
"""

def minEatingSpeed(piles: List[int], h: int) -> int:
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

print(f"Koko min speed: {minEatingSpeed([3,6,7,11], 8)}")   # 4
print(f"Koko min speed: {minEatingSpeed([30,11,23,4,20], 5)}")  # 30

# ─────────────────────────────────────────────
# PATTERN 3: Find Minimum in Rotated Sorted Array
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("PATTERN 3: Find Minimum in Rotated Sorted Array")
print("=" * 60)

"""
Key insight: The minimum is always on the UNSORTED side.
If nums[mid] > nums[hi], minimum is in right half.
Otherwise, minimum is in left half (including mid).
"""

def findMin(nums: List[int]) -> int:
    lo, hi = 0, len(nums) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if nums[mid] > nums[hi]:
            lo = mid + 1   # min is in right half
        else:
            hi = mid       # min is in left half (including mid)
    return nums[lo]

print(findMin([3,4,5,1,2]))   # 1
print(findMin([4,5,6,7,0,1])) # 0
print(findMin([11,13,15,17])) # 11

# ─────────────────────────────────────────────
# PATTERN 4: Binary Search on 2D Matrix
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("PATTERN 4: Binary Search on 2D Matrix")
print("=" * 60)

"""
Treat the m×n matrix as a flat sorted array of m*n elements.
Map index i → row = i // n, col = i % n
"""

def searchMatrix(matrix: List[List[int]], target: int) -> bool:
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

matrix = [[1,3,5,7],[10,11,16,20],[23,30,34,60]]
print(searchMatrix(matrix, 3))   # True
print(searchMatrix(matrix, 13))  # False

# ─────────────────────────────────────────────
# INTERVIEW Q&A
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("INTERVIEW Q&A")
print("=" * 60)

qa = """
Q1: What's the difference between lo < hi and lo <= hi?
A1: lo <= hi → used when we return inside the loop (exact match).
    lo < hi  → used when we want lo == hi at termination (lower/upper bound).
    Getting this right is the hardest part of binary search.

Q2: Why mid = lo + (hi - lo) // 2 instead of (lo + hi) // 2?
A2: Overflow prevention in languages with fixed int size (Java/C++).
    In Python, integers are unbounded so both work, but the former
    is good habit and shows interviewer you know the issue.

Q3: How do you binary search on an infinite/unknown-length array?
A3: Use exponential search: find bounds first.
    Start with hi=1, double until arr[hi] >= target.
    Then binary search in [hi//2, hi].

Q4: What is binary search on the answer?
A4: Instead of searching for a value in an array, search for the
    answer value in its possible range. Requires a monotonic condition
    function (can_do(x): bool). Very powerful for optimization problems.

Q5: Can binary search work on unsorted data?
A5: Only if there's a monotonic property. E.g., finding a peak element
    (LC 162) works because we can determine which direction the peak is.

Q6: When does binary search give O(log n) vs O(n)?
A6: O(log n): sorted array, binary search on answer with O(1) check.
    O(n log n): if the feasibility check is O(n) — still better than O(n²).

Q7: What is the invariant in binary search?
A7: The target (or answer) always lies within [lo, hi] at every iteration.
    Proving this invariant is how you verify your binary search is correct.
"""
print(qa)

# ─────────────────────────────────────────────
# COMPLETE CHEAT SHEET
# ─────────────────────────────────────────────
cheat = """
BINARY SEARCH CHEAT SHEET
──────────────────────────

STANDARD (find exact value):
  lo, hi = 0, n-1
  while lo <= hi:
      mid = (lo+hi)//2
      if nums[mid] == target: return mid
      elif nums[mid] < target: lo = mid+1
      else: hi = mid-1
  return -1

LOWER BOUND (first index where nums[i] >= target):
  lo, hi = 0, n
  while lo < hi:
      mid = (lo+hi)//2
      if nums[mid] < target: lo = mid+1
      else: hi = mid
  return lo

UPPER BOUND (first index where nums[i] > target):
  lo, hi = 0, n
  while lo < hi:
      mid = (lo+hi)//2
      if nums[mid] <= target: lo = mid+1
      else: hi = mid
  return lo

BINARY SEARCH ON ANSWER (find minimum satisfying condition):
  lo, hi = min_val, max_val
  while lo < hi:
      mid = (lo+hi)//2
      if can_do(mid): hi = mid
      else: lo = mid+1
  return lo
"""
print(cheat)
