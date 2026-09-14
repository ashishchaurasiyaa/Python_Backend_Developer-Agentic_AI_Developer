"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DSA — Arrays: Two Pointer, Sliding Window, Prefix Sum, Monotonic Stack
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from collections import deque, defaultdict, OrderedDict
import heapq


# ═══════════════════════════════════════════════════════════════
# SECTION 1: TWO POINTER PATTERN
# ═══════════════════════════════════════════════════════════════
"""
CONCEPT:
  Use two indices (left, right) moving toward or away from each other.
  Avoids nested loops → reduces O(n²) to O(n).

WHEN TO USE:
  - Array is sorted (or can be sorted)
  - Finding pairs/triplets that satisfy a condition
  - Comparing elements from both ends
  - Partitioning arrays

TEMPLATE — Opposite ends:
    left, right = 0, len(arr) - 1
    while left < right:
        if condition_met:
            # record answer
            left += 1
            right -= 1
        elif too_small:
            left += 1
        else:
            right -= 1

TEMPLATE — Same direction (fast/slow):
    slow = 0
    for fast in range(len(arr)):
        if condition:
            arr[slow] = arr[fast]
            slow += 1
"""


# ─────────────────────────────────────────────────────────────
# Problem 1: Two Sum II — Input Array Is Sorted (LeetCode 167)
# ─────────────────────────────────────────────────────────────
"""
PROBLEM:
  Given a 1-indexed sorted array, return indices of two numbers that add to target.
  Exactly one solution guaranteed. Cannot use same element twice.

APPROACH:
  Left pointer starts at beginning, right at end.
  If sum < target → move left right (need bigger number).
  If sum > target → move right left (need smaller number).
  If sum == target → return indices.
"""

def two_sum_sorted(numbers: list[int], target: int) -> list[int]:
    left, right = 0, len(numbers) - 1
    while left < right:
        current_sum = numbers[left] + numbers[right]
        if current_sum == target:
            return [left + 1, right + 1]  # 1-indexed
        elif current_sum < target:
            left += 1
        else:
            right -= 1
    return []  # no solution (problem guarantees one exists)
# Time: O(n) | Space: O(1)

# Follow-up edge cases:
# - All elements equal: [3, 3], target=6 → handled correctly
# - Negative numbers: [-3, 0, 3], target=0 → works
# - Two-element array: always check first and last


# ─────────────────────────────────────────────────────────────
# Problem 2: 3Sum (LeetCode 15) — find all unique triplets summing to 0
# ─────────────────────────────────────────────────────────────
"""
PROBLEM:
  Given integer array nums, return all unique triplets [a, b, c] such that
  a + b + c == 0. Solution set must not contain duplicate triplets.

APPROACH:
  Sort array. Fix one element (i), then use two-pointer on the rest.
  Skip duplicates after finding a valid triplet, and when advancing i.
"""

def three_sum(nums: list[int]) -> list[list[int]]:
    nums.sort()
    result = []
    n = len(nums)

    for i in range(n - 2):
        # Skip duplicate values for the fixed element
        if i > 0 and nums[i] == nums[i - 1]:
            continue
        # Optimization: if smallest possible sum > 0, break
        if nums[i] > 0:
            break

        left, right = i + 1, n - 1
        while left < right:
            total = nums[i] + nums[left] + nums[right]
            if total == 0:
                result.append([nums[i], nums[left], nums[right]])
                # Skip duplicates for left and right
                while left < right and nums[left] == nums[left + 1]:
                    left += 1
                while left < right and nums[right] == nums[right - 1]:
                    right -= 1
                left += 1
                right -= 1
            elif total < 0:
                left += 1
            else:
                right -= 1

    return result
# Time: O(n²) | Space: O(1) excluding output

# Follow-up edge cases:
# - All zeros: [0,0,0,0] → [[0,0,0]]
# - No valid triplet: [1,2,3] → []
# - All negatives: [-4,-3,-2,-1] → []


# ─────────────────────────────────────────────────────────────
# Problem 3: Container With Most Water (LeetCode 11)
# ─────────────────────────────────────────────────────────────
"""
PROBLEM:
  Given n vertical lines at positions 0..n-1 with heights height[i],
  find two lines that together with x-axis form a container holding most water.

APPROACH:
  Width = right - left. Height = min(height[left], height[right]).
  Always move the pointer with the shorter line inward —
  moving the taller one can only reduce area (width shrinks, height can't grow).
"""

def max_area(height: list[int]) -> int:
    left, right = 0, len(height) - 1
    max_water = 0
    while left < right:
        width = right - left
        h = min(height[left], height[right])
        max_water = max(max_water, width * h)
        if height[left] <= height[right]:
            left += 1
        else:
            right -= 1
    return max_water
# Time: O(n) | Space: O(1)

# Follow-up edge cases:
# - Equal heights: [3, 3] → 3
# - Monotonically increasing: [1,2,3,4,5] → answer at ends first


# ─────────────────────────────────────────────────────────────
# Problem 4: Trapping Rain Water (LeetCode 42)
# ─────────────────────────────────────────────────────────────
"""
PROBLEM:
  Given heights of an elevation map, compute how much water it can trap after raining.

APPROACH (Two Pointer — O(1) space):
  At each position, trapped water = min(max_left, max_right) - height[i].
  Maintain left_max and right_max as we move pointers inward.
  Process the side with the smaller max — because that side's water level is capped
  by its own max (the other side is guaranteed to be >= it).
"""

def trap_rain_water(height: list[int]) -> int:
    if not height:
        return 0
    left, right = 0, len(height) - 1
    left_max = right_max = 0
    water = 0

    while left < right:
        if height[left] <= height[right]:
            if height[left] >= left_max:
                left_max = height[left]
            else:
                water += left_max - height[left]
            left += 1
        else:
            if height[right] >= right_max:
                right_max = height[right]
            else:
                water += right_max - height[right]
            right -= 1

    return water
# Time: O(n) | Space: O(1)

# Follow-up edge cases:
# - Flat surface: [3,3,3] → 0
# - Valley: [3,0,3] → 3
# - Single peak: [0,1,0] → 0


# ═══════════════════════════════════════════════════════════════
# SECTION 2: SLIDING WINDOW PATTERN
# ═══════════════════════════════════════════════════════════════
"""
CONCEPT:
  Maintain a window [left, right] over an array/string.
  Expand right to include elements; shrink left when constraint violated.

WHEN TO USE:
  - Contiguous subarray/substring problems
  - "Maximum/minimum length subarray with property X"
  - "Longest substring with at most K distinct chars"

TEMPLATE — Fixed window:
    window_sum = sum(arr[:k])
    max_sum = window_sum
    for i in range(k, len(arr)):
        window_sum += arr[i] - arr[i - k]
        max_sum = max(max_sum, window_sum)

TEMPLATE — Variable window:
    left = 0
    state = {}  # or counter
    result = 0
    for right in range(len(arr)):
        # expand: add arr[right] to window
        state[arr[right]] = state.get(arr[right], 0) + 1
        # shrink: while constraint violated
        while <constraint violated>:
            state[arr[left]] -= 1
            if state[arr[left]] == 0:
                del state[arr[left]]
            left += 1
        result = max(result, right - left + 1)
    return result
"""


# ─────────────────────────────────────────────────────────────
# Problem 5: Maximum Sum Subarray of Size K
# ─────────────────────────────────────────────────────────────
"""
PROBLEM:
  Given an integer array and integer k, find the maximum sum of any
  contiguous subarray of size exactly k.

APPROACH:
  Fixed sliding window. Compute sum of first k elements, then slide:
  add next element, remove leftmost element.
"""

def max_sum_subarray_k(arr: list[int], k: int) -> int:
    if len(arr) < k:
        return 0
    window_sum = sum(arr[:k])
    max_sum = window_sum
    for i in range(k, len(arr)):
        window_sum += arr[i] - arr[i - k]
        max_sum = max(max_sum, window_sum)
    return max_sum
# Time: O(n) | Space: O(1)

# Follow-up edge cases:
# - k == len(arr): sum entire array
# - All negative: [-1,-2,-3], k=2 → -3 (max of negatives)
# - k == 1: return max element


# ─────────────────────────────────────────────────────────────
# Problem 6: Longest Substring Without Repeating Characters (LeetCode 3)
# ─────────────────────────────────────────────────────────────
"""
PROBLEM:
  Given string s, find length of the longest substring without repeating characters.

APPROACH:
  Variable window. Use a set to track characters in current window.
  When a duplicate is found, shrink from left until duplicate is removed.
"""

def length_of_longest_substring(s: str) -> int:
    char_set = set()
    left = 0
    max_len = 0

    for right in range(len(s)):
        # Shrink window until no duplicate
        while s[right] in char_set:
            char_set.remove(s[left])
            left += 1
        char_set.add(s[right])
        max_len = max(max_len, right - left + 1)

    return max_len
# Time: O(n) | Space: O(min(n, alphabet_size))

# Optimized version using last-seen index (avoids inner while loop):
def length_of_longest_substring_v2(s: str) -> int:
    last_seen = {}  # char -> last index
    left = 0
    max_len = 0
    for right, char in enumerate(s):
        if char in last_seen and last_seen[char] >= left:
            left = last_seen[char] + 1
        last_seen[char] = right
        max_len = max(max_len, right - left + 1)
    return max_len
# Time: O(n) | Space: O(min(n, alphabet_size))

# Follow-up edge cases:
# - Empty string: "" → 0
# - All same chars: "aaaa" → 1
# - All unique: "abcd" → 4
# - Unicode characters: works the same way


# ─────────────────────────────────────────────────────────────
# Problem 7: Minimum Window Substring (LeetCode 76)
# ─────────────────────────────────────────────────────────────
"""
PROBLEM:
  Given strings s and t, return the minimum window in s that contains
  all characters of t (including duplicates). Return "" if none exists.

APPROACH:
  Variable window. Track how many distinct required chars are satisfied.
  'need' dict: required counts. 'have' dict: current window counts.
  'formed' tracks how many chars meet their required frequency.
  When all chars satisfied, try to shrink from left to minimize window.
"""

def min_window_substring(s: str, t: str) -> str:
    if not t or not s:
        return ""

    need = defaultdict(int)
    for c in t:
        need[c] += 1

    required = len(need)  # number of unique chars needed
    formed = 0            # unique chars currently satisfied

    have = defaultdict(int)
    left = 0
    min_len = float('inf')
    result_start = 0

    for right in range(len(s)):
        c = s[right]
        have[c] += 1
        # Check if this character's frequency is now satisfied
        if c in need and have[c] == need[c]:
            formed += 1

        # Try to shrink window from left
        while formed == required:
            # Update result if this window is smaller
            window_len = right - left + 1
            if window_len < min_len:
                min_len = window_len
                result_start = left

            # Remove leftmost character
            left_char = s[left]
            have[left_char] -= 1
            if left_char in need and have[left_char] < need[left_char]:
                formed -= 1
            left += 1

    return s[result_start:result_start + min_len] if min_len != float('inf') else ""
# Time: O(|s| + |t|) | Space: O(|s| + |t|)

# Follow-up edge cases:
# - t longer than s: impossible → ""
# - t has duplicate chars: "aa" — need count handles this
# - s == t: return s


# ═══════════════════════════════════════════════════════════════
# SECTION 3: PREFIX SUM PATTERN
# ═══════════════════════════════════════════════════════════════
"""
CONCEPT:
  prefix[i] = sum of arr[0..i-1]
  Sum of arr[l..r] = prefix[r+1] - prefix[l]
  Precompute in O(n), answer each query in O(1).

WHEN TO USE:
  - Range sum queries
  - Subarray sum equals target
  - 2D range sum queries (extend to 2D prefix sum)
"""


# ─────────────────────────────────────────────────────────────
# Problem 8: Subarray Sum Equals K (LeetCode 560)
# ─────────────────────────────────────────────────────────────
"""
PROBLEM:
  Given integer array nums and integer k, return the number of subarrays
  whose sum equals k. Array may have negative numbers.

APPROACH:
  Use prefix sum with a hash map.
  If prefix_sum[j] - prefix_sum[i] == k, then subarray [i+1..j] sums to k.
  Equivalently, prefix_sum[i] = prefix_sum[j] - k.
  Store count of each prefix sum seen so far.
"""

def subarray_sum_equals_k(nums: list[int], k: int) -> int:
    count = 0
    prefix_sum = 0
    # prefix_count[x] = number of times prefix sum x has been seen
    prefix_count = defaultdict(int)
    prefix_count[0] = 1  # empty prefix (sum = 0) exists once

    for num in nums:
        prefix_sum += num
        # If (prefix_sum - k) was seen before, those subarrays sum to k
        count += prefix_count[prefix_sum - k]
        prefix_count[prefix_sum] += 1

    return count
# Time: O(n) | Space: O(n)

# Follow-up edge cases:
# - k=0: counts subarrays that sum to 0 (including empty... handled by init)
# - Negative numbers: handled naturally by hash map approach
# - Single element equal to k: counted correctly


# ─────────────────────────────────────────────────────────────
# Problem 9: Range Sum Query — Immutable (LeetCode 303)
# ─────────────────────────────────────────────────────────────
"""
PROBLEM:
  Given integer array nums, handle multiple queries sumRange(left, right)
  returning sum of elements between indices left and right (inclusive).

APPROACH:
  Precompute prefix sums in __init__. Answer each query in O(1).
"""

class NumArray:
    def __init__(self, nums: list[int]):
        n = len(nums)
        self.prefix = [0] * (n + 1)
        for i in range(n):
            self.prefix[i + 1] = self.prefix[i] + nums[i]

    def sumRange(self, left: int, right: int) -> int:
        return self.prefix[right + 1] - self.prefix[left]
# __init__: O(n) | sumRange: O(1) | Space: O(n)

# Follow-up edge cases:
# - Single element query: left == right → prefix[right+1] - prefix[right] = nums[right]
# - Full array: left=0, right=n-1 → prefix[n] - prefix[0]


# ═══════════════════════════════════════════════════════════════
# SECTION 4: MONOTONIC STACK
# ═══════════════════════════════════════════════════════════════
"""
CONCEPT:
  A stack that maintains elements in monotonically increasing or decreasing order.
  When a new element violates the order, pop elements until order is restored.
  Popped elements found their "answer" (next greater/smaller element).

WHEN TO USE:
  - Next greater/smaller element problems
  - "Span" problems (how far back is the last element >= current)
  - Histogram problems
  - Temperature / stock span problems

TEMPLATE — Next Greater Element (monotonic decreasing stack):
    stack = []  # stores indices
    result = [-1] * n
    for i in range(n):
        while stack and arr[stack[-1]] < arr[i]:
            idx = stack.pop()
            result[idx] = arr[i]  # arr[i] is next greater for arr[idx]
        stack.append(i)
    return result
"""


# ─────────────────────────────────────────────────────────────
# Problem 10: Next Greater Element I (LeetCode 496)
# ─────────────────────────────────────────────────────────────
"""
PROBLEM:
  Given two arrays nums1 and nums2 (nums1 is a subset of nums2),
  for each element in nums1, find the next greater element in nums2.
  Return -1 if none exists.

APPROACH:
  Build a next_greater map for nums2 using monotonic stack.
  Then look up each element of nums1 in the map.
"""

def next_greater_element(nums1: list[int], nums2: list[int]) -> list[int]:
    next_greater = {}  # element -> next greater element in nums2
    stack = []         # monotonic decreasing stack

    for num in nums2:
        # Pop elements smaller than current — current is their next greater
        while stack and stack[-1] < num:
            next_greater[stack.pop()] = num
        stack.append(num)

    # Remaining elements in stack have no next greater
    while stack:
        next_greater[stack.pop()] = -1

    return [next_greater[n] for n in nums1]
# Time: O(|nums1| + |nums2|) | Space: O(|nums2|)

# Follow-up edge cases:
# - nums2 sorted ascending: all -1 except last element
# - All equal: all -1
# - nums1 has one element: single lookup


# ─────────────────────────────────────────────────────────────
# Problem 11: Daily Temperatures (LeetCode 739)
# ─────────────────────────────────────────────────────────────
"""
PROBLEM:
  Given temperatures array, for each day return number of days until a
  warmer temperature. If no future warmer day exists, return 0.

APPROACH:
  Monotonic decreasing stack of indices.
  When we find a warmer temperature, pop cooler days and compute distance.
"""

def daily_temperatures(temperatures: list[int]) -> list[int]:
    n = len(temperatures)
    result = [0] * n
    stack = []  # indices, temperatures[stack[-1]] is decreasing

    for i, temp in enumerate(temperatures):
        # Pop all days cooler than today
        while stack and temperatures[stack[-1]] < temp:
            j = stack.pop()
            result[j] = i - j  # days waited
        stack.append(i)

    return result
# Time: O(n) | Space: O(n)

# Follow-up edge cases:
# - Sorted descending [5,4,3,2]: all 0 (stack never pops)
# - Sorted ascending [1,2,3,4]: result = [1,1,1,0]
# - Single element: [72] → [0]


# ─────────────────────────────────────────────────────────────
# Problem 12: Largest Rectangle in Histogram (LeetCode 84)
# ─────────────────────────────────────────────────────────────
"""
PROBLEM:
  Given array of bar heights in a histogram (width=1 each),
  find the area of the largest rectangle.

APPROACH:
  Monotonic increasing stack of indices.
  When a bar shorter than stack top is found, pop and compute area:
    width = i - stack[-1] - 1 (or i if stack empty)
    height = heights[popped_index]
  Append sentinel 0 at end to flush remaining stack.
"""

def largest_rectangle_histogram(heights: list[int]) -> int:
    stack = []  # indices, heights are increasing
    max_area = 0
    heights = heights + [0]  # sentinel to flush stack at end

    for i, h in enumerate(heights):
        while stack and heights[stack[-1]] > h:
            height = heights[stack.pop()]
            # Width extends from current i back to the new stack top
            width = i if not stack else i - stack[-1] - 1
            max_area = max(max_area, height * width)
        stack.append(i)

    return max_area
# Time: O(n) | Space: O(n)

# Follow-up edge cases:
# - Single bar: [5] → 5
# - All same height: [3,3,3] → 9
# - Staircase ascending: [1,2,3,4,5] → 9 (3+3+3)
# - Valley: [3,1,3] → 3 (not 3*3 because middle is 1)


# ═══════════════════════════════════════════════════════════════
# QUICK REFERENCE SUMMARY
# ═══════════════════════════════════════════════════════════════
"""
PATTERN          | KEY IDEA                          | TIME  | SPACE
─────────────────┼───────────────────────────────────┼───────┼──────
Two Pointer      | Opposite/same direction pointers  | O(n)  | O(1)
Sliding Window   | Expand right, shrink left          | O(n)  | O(k)
Prefix Sum       | Precompute cumulative sums         | O(n)  | O(n)
Monotonic Stack  | Maintain order, pop for answers   | O(n)  | O(n)

CHOOSE BY PROBLEM TYPE:
  - Sorted array, pair/triplet sum    → Two Pointer
  - Contiguous subarray, no negatives → Sliding Window (can also use Two Pointer)
  - Range sum queries, subarray sum k → Prefix Sum
  - Next greater/smaller, histogram   → Monotonic Stack
"""


# ═══════════════════════════════════════════════════════════════
# TESTS — run this file to verify all solutions
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Two Sum II
    assert two_sum_sorted([2, 7, 11, 15], 9) == [1, 2]
    assert two_sum_sorted([2, 3, 4], 6) == [1, 3]
    print("two_sum_sorted: OK")

    # 3Sum
    assert sorted(map(sorted, three_sum([-1, 0, 1, 2, -1, -4]))) == [[-1, -1, 2], [-1, 0, 1]]
    assert three_sum([0, 1, 1]) == []
    assert three_sum([0, 0, 0]) == [[0, 0, 0]]
    print("three_sum: OK")

    # Container with most water
    assert max_area([1, 8, 6, 2, 5, 4, 8, 3, 7]) == 49
    assert max_area([1, 1]) == 1
    print("max_area: OK")

    # Trapping rain water
    assert trap_rain_water([0, 1, 0, 2, 1, 0, 1, 3, 2, 1, 2, 1]) == 6
    assert trap_rain_water([4, 2, 0, 3, 2, 5]) == 9
    print("trap_rain_water: OK")

    # Max sum subarray k
    assert max_sum_subarray_k([2, 1, 5, 1, 3, 2], 3) == 9
    assert max_sum_subarray_k([2, 3, 4, 1, 5], 2) == 7
    print("max_sum_subarray_k: OK")

    # Longest substring without repeating
    assert length_of_longest_substring("abcabcbb") == 3
    assert length_of_longest_substring("bbbbb") == 1
    assert length_of_longest_substring("pwwkew") == 3
    assert length_of_longest_substring_v2("abcabcbb") == 3
    print("length_of_longest_substring: OK")

    # Minimum window substring
    assert min_window_substring("ADOBECODEBANC", "ABC") == "BANC"
    assert min_window_substring("a", "a") == "a"
    assert min_window_substring("a", "aa") == ""
    print("min_window_substring: OK")

    # Subarray sum equals k
    assert subarray_sum_equals_k([1, 1, 1], 2) == 2
    assert subarray_sum_equals_k([1, 2, 3], 3) == 2
    print("subarray_sum_equals_k: OK")

    # Range sum query
    na = NumArray([-2, 0, 3, -5, 2, -1])
    assert na.sumRange(0, 2) == 1
    assert na.sumRange(2, 5) == -1
    assert na.sumRange(0, 5) == -3
    print("NumArray sumRange: OK")

    # Next greater element
    assert next_greater_element([4, 1, 2], [1, 3, 4, 2]) == [-1, 3, -1]
    assert next_greater_element([2, 4], [1, 2, 3, 4]) == [3, -1]
    print("next_greater_element: OK")

    # Daily temperatures
    assert daily_temperatures([73, 74, 75, 71, 69, 72, 76, 73]) == [1, 1, 4, 2, 1, 1, 0, 0]
    assert daily_temperatures([30, 40, 50, 60]) == [1, 1, 1, 0]
    print("daily_temperatures: OK")

    # Largest rectangle in histogram
    assert largest_rectangle_histogram([2, 1, 5, 6, 2, 3]) == 10
    assert largest_rectangle_histogram([2, 4]) == 4
    print("largest_rectangle_histogram: OK")

    print("\nAll tests passed!")
