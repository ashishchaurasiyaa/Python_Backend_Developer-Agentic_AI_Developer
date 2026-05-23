"""
╔══════════════════════════════════════════════════════════════════╗
║       TWO POINTERS & SLIDING WINDOW — Complete Theory Guide      ║
╚══════════════════════════════════════════════════════════════════╝

WHAT ARE TWO POINTERS?
───────────────────────
Two Pointers is a technique where we use two index variables to traverse
a data structure, usually in opposite directions or at different speeds.

WHAT IS SLIDING WINDOW?
────────────────────────
Sliding Window is a special case of two pointers (same direction) that
maintains a contiguous subarray/substring and slides it across the input.

WHY USE THEM?
──────────────
- Reduce O(n²) brute force to O(n)
- Avoid nested loops when operating on subarrays/pairs
- Constant extra space (no hash map needed in many cases)

COMPLEXITY TABLE
─────────────────────────────────────────────────────────────────
Pattern                    Time      Space    Common Use
─────────────────────────────────────────────────────────────────
Two Pointers (opposite)    O(n)      O(1)     Sorted array pairs
Two Pointers (same dir)    O(n)      O(1)     Remove, partition
Sliding Window (fixed k)   O(n)      O(1)     Max/min of size-k
Sliding Window (variable)  O(n)      O(k)     Longest/shortest
─────────────────────────────────────────────────────────────────
"""

from typing import List
from collections import defaultdict

# ─────────────────────────────────────────────
# 1. TWO POINTERS — OPPOSITE ENDS
# ─────────────────────────────────────────────
print("=" * 60)
print("TYPE 1: Two Pointers — Opposite Ends")
print("=" * 60)

"""
WHEN TO USE:
  - Sorted array (or can be sorted)
  - Looking for a pair with a target sum
  - Container problems (maximize area)
  - Palindrome check

TEMPLATE:
  lo, hi = 0, len(arr) - 1
  while lo < hi:
      if condition(arr[lo], arr[hi]):
          lo += 1, hi -= 1  # or record answer
      elif too_small:
          lo += 1
      else:
          hi -= 1
"""

def two_sum_sorted(nums: List[int], target: int):
    """Two Sum II — sorted array. Find pair summing to target."""
    lo, hi = 0, len(nums) - 1
    while lo < hi:
        s = nums[lo] + nums[hi]
        if s == target:
            return [lo + 1, hi + 1]  # 1-indexed
        elif s < target:
            lo += 1
        else:
            hi -= 1
    return []

print(two_sum_sorted([2, 7, 11, 15], 9))   # [1, 2]
print(two_sum_sorted([2, 3, 4], 6))         # [1, 3]

def is_palindrome(s: str) -> bool:
    """Check if string is a palindrome using two pointers."""
    lo, hi = 0, len(s) - 1
    while lo < hi:
        if s[lo] != s[hi]:
            return False
        lo += 1
        hi -= 1
    return True

print(is_palindrome("racecar"))  # True
print(is_palindrome("hello"))    # False

# ─────────────────────────────────────────────
# 2. TWO POINTERS — SAME DIRECTION
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("TYPE 2: Two Pointers — Same Direction (Fast/Slow)")
print("=" * 60)

"""
WHEN TO USE:
  - In-place modifications (remove duplicates, move zeros)
  - Partitioning
  - Cycle detection (Floyd's algorithm)

TEMPLATE:
  slow = 0
  for fast in range(len(arr)):
      if condition(arr[fast]):
          arr[slow] = arr[fast]
          slow += 1
  return slow  # new length
"""

def move_zeros(nums: List[int]) -> List[int]:
    """Move all zeros to end while maintaining relative order of non-zeros."""
    slow = 0
    for fast in range(len(nums)):
        if nums[fast] != 0:
            nums[slow], nums[fast] = nums[fast], nums[slow]
            slow += 1
    return nums

print(move_zeros([0, 1, 0, 3, 12]))  # [1, 3, 12, 0, 0]

def remove_duplicates(nums: List[int]) -> int:
    """Remove duplicates in-place from sorted array. Return new length."""
    slow = 1
    for fast in range(1, len(nums)):
        if nums[fast] != nums[fast - 1]:
            nums[slow] = nums[fast]
            slow += 1
    return slow

nums = [1, 1, 2, 2, 3]
k = remove_duplicates(nums)
print(nums[:k])  # [1, 2, 3]

# ─────────────────────────────────────────────
# 3. SLIDING WINDOW — FIXED SIZE
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("TYPE 3: Sliding Window — Fixed Size k")
print("=" * 60)

"""
WHEN TO USE:
  - Maximum/minimum sum of exactly k elements
  - Average of every k-length window
  - Count distinct elements in every window of size k

TEMPLATE:
  window_sum = sum(nums[:k])
  result = [window_sum]
  for i in range(k, len(nums)):
      window_sum += nums[i] - nums[i - k]
      result.append(window_sum)
  return result
"""

def max_sum_subarray_k(nums: List[int], k: int) -> int:
    """Find maximum sum of any contiguous subarray of size k."""
    window_sum = sum(nums[:k])
    max_sum = window_sum
    for i in range(k, len(nums)):
        window_sum += nums[i] - nums[i - k]  # slide: add new, remove old
        max_sum = max(max_sum, window_sum)
    return max_sum

print(max_sum_subarray_k([2, 1, 5, 1, 3, 2], 3))  # 9 (5+1+3)
print(max_sum_subarray_k([1, 4, 2, 10, 23, 3, 1, 0, 20], 4))  # 39

# ─────────────────────────────────────────────
# 4. SLIDING WINDOW — VARIABLE SIZE
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("TYPE 4: Sliding Window — Variable Size")
print("=" * 60)

"""
WHEN TO USE:
  - Longest/shortest subarray meeting a condition
  - Minimum window substring
  - Longest substring without repeating characters

TEMPLATE (find LONGEST window):
  lo = 0
  result = 0
  state = {}  # or Counter

  for hi in range(len(s)):
      # Expand window: add s[hi] to state
      state[s[hi]] += 1

      # Shrink window while condition violated
      while INVALID(state):
          state[s[lo]] -= 1
          lo += 1

      # Window [lo..hi] is now valid
      result = max(result, hi - lo + 1)

  return result

TEMPLATE (find SHORTEST window):
  lo = 0
  result = float('inf')

  for hi in range(len(nums)):
      # Expand window
      ...
      # Shrink while VALID (try to minimize)
      while VALID(state):
          result = min(result, hi - lo + 1)
          # Remove lo from window
          lo += 1

  return result if result != float('inf') else 0
"""

def longest_no_repeat(s: str) -> int:
    """Longest substring without repeating characters."""
    char_index = {}  # char → last seen index
    lo = 0
    result = 0
    for hi, ch in enumerate(s):
        if ch in char_index and char_index[ch] >= lo:
            lo = char_index[ch] + 1
        char_index[ch] = hi
        result = max(result, hi - lo + 1)
    return result

print(longest_no_repeat("abcabcbb"))  # 3
print(longest_no_repeat("bbbbb"))     # 1
print(longest_no_repeat("pwwkew"))    # 3

def min_window_substring(s: str, t: str) -> str:
    """Minimum window in s containing all chars of t."""
    if not t: return ""
    need = defaultdict(int)
    for ch in t:
        need[ch] += 1
    have = defaultdict(int)
    formed = 0
    required = len(need)
    lo = 0
    result = ""
    result_len = float('inf')

    for hi, ch in enumerate(s):
        have[ch] += 1
        if ch in need and have[ch] == need[ch]:
            formed += 1
        while formed == required:
            if hi - lo + 1 < result_len:
                result_len = hi - lo + 1
                result = s[lo:hi+1]
            have[s[lo]] -= 1
            if s[lo] in need and have[s[lo]] < need[s[lo]]:
                formed -= 1
            lo += 1
    return result

print(min_window_substring("ADOBECODEBANC", "ABC"))  # "BANC"

# ─────────────────────────────────────────────
# 5. WHEN TO USE WHICH PATTERN
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("DECISION GUIDE")
print("=" * 60)

decision = """
QUESTION TO ASK              → TECHNIQUE
─────────────────────────────────────────────────────────
Find a pair with target sum? → Two Pointers (opposite, sorted)
Is the array sorted?         → Two Pointers preferred
Find triplets/quadruplets?   → Sort + Two Pointers inner loop
Remove elements in-place?    → Fast/Slow two pointers
Subarray of EXACTLY k size?  → Fixed sliding window
Longest/shortest subarray?   → Variable sliding window
Need hash map for state?     → Variable sliding window + Counter
"""
print(decision)

# ─────────────────────────────────────────────
# 6. THREE SUM — Two Pointers Classic
# ─────────────────────────────────────────────
print("=" * 60)
print("CLASSIC: 3Sum — Sort + Two Pointers")
print("=" * 60)

def three_sum(nums: List[int]) -> List[List[int]]:
    """
    Find all unique triplets that sum to zero.
    Time: O(n²) | Space: O(1) excluding output
    """
    nums.sort()
    result = []
    for i in range(len(nums) - 2):
        if i > 0 and nums[i] == nums[i - 1]:
            continue   # skip duplicate pivots
        lo, hi = i + 1, len(nums) - 1
        while lo < hi:
            s = nums[i] + nums[lo] + nums[hi]
            if s == 0:
                result.append([nums[i], nums[lo], nums[hi]])
                while lo < hi and nums[lo] == nums[lo + 1]: lo += 1
                while lo < hi and nums[hi] == nums[hi - 1]: hi -= 1
                lo += 1; hi -= 1
            elif s < 0:
                lo += 1
            else:
                hi -= 1
    return result

print(three_sum([-1, 0, 1, 2, -1, -4]))  # [[-1,-1,2],[-1,0,1]]

# ─────────────────────────────────────────────
# 7. INTERVIEW Q&A
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("INTERVIEW Q&A")
print("=" * 60)

qa = """
Q1: What is the key insight of the sliding window technique?
A1: We can reuse computation from the previous window. Instead of
    recomputing from scratch (O(kn)), we add one element and remove
    one element (O(n) total). The window "slides" without restarting.

Q2: When can't we use two pointers?
A2: When the array is unsorted and can't be sorted (e.g., need original
    indices), or when we need to consider all pairs (not just optimal ones).

Q3: How do you handle duplicates in 3Sum?
A3: Sort the array. After fixing one pointer, skip duplicates at all
    three positions to avoid repeating triplets.

Q4: What's the difference between fixed and variable sliding window?
A4: Fixed: window size is constant (k). Shrinks and grows by 1 each step.
    Variable: window size changes based on a condition. Expand hi freely,
    shrink lo when condition is violated.

Q5: How do you identify that a problem can use sliding window?
A5: Look for: "subarray", "substring", "contiguous", "window of size k",
    "longest/shortest subarray where [condition]". The condition must
    be checkable incrementally (adding/removing one element).

Q6: Can sliding window work on 2D arrays?
A6: Yes, but it's more complex. For 2D, fix one dimension and slide the
    other. Or use prefix sums for 2D range queries.

Q7: What is the amortized complexity of variable sliding window?
A7: O(n) — each element enters and exits the window at most once,
    so the total number of operations is 2n.
"""
print(qa)
