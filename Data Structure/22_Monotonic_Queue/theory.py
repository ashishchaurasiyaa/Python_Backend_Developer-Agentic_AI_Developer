"""
22 — Monotonic Queue (Deque) — Theory
=======================================
Level: Intermediate → Advanced
"""
from __future__ import annotations
from collections import deque
from typing import List

# ════════════════════════════════════════════════════════════
# WHAT & WHY
# ════════════════════════════════════════════════════════════
"""
MONOTONIC QUEUE = a deque where elements are kept in monotonically
increasing OR decreasing order.

WHY: Sliding window max/min in O(1) per element → O(n) total.
     Without it: O(n×k) brute force for window of size k.

DIFFERENCE from Monotonic Stack:
  Stack: no removal from front (used for next greater element).
  Queue: remove from BOTH ends (used for sliding window max/min).

KEY OPERATIONS:
  1. Pop from BACK when new element breaks monotonic order
  2. Pop from FRONT when element is out of window (index too old)
  3. Front of deque = current window max (for decreasing deque)
"""

# ════════════════════════════════════════════════════════════
# COMPLEXITY
# ════════════════════════════════════════════════════════════
"""
Operation                   Time    Space
──────────────────────────────────────────
Sliding window max/min      O(n)    O(k)
(each element pushed/popped at most once)

Brute force sliding window  O(n×k)  O(1)
"""

# ════════════════════════════════════════════════════════════
# PATTERN 1: Sliding Window Maximum
# ════════════════════════════════════════════════════════════

def sliding_window_max(nums: List[int], k: int) -> List[int]:
    """
    Maximum in every window of size k.
    Deque stores INDICES, keeps values in DECREASING order.

    For each new element nums[i]:
      1. Remove indices from BACK if nums[dq[-1]] <= nums[i]  (they can never be max)
      2. Push i to BACK
      3. Remove from FRONT if dq[0] <= i - k  (out of window)
      4. Front = index of current max
    """
    dq = deque()   # stores indices, values decreasing
    result = []

    for i, n in enumerate(nums):
        # Remove smaller elements from back (they'll never be max in this window)
        while dq and nums[dq[-1]] <= n:
            dq.pop()
        dq.append(i)
        # Remove front if outside window
        if dq[0] <= i - k:
            dq.popleft()
        # Start collecting after first full window
        if i >= k - 1:
            result.append(nums[dq[0]])

    return result

print("Sliding max k=3:", sliding_window_max([1,3,-1,-3,5,3,6,7], 3))
# [3,3,5,5,6,7]


# ════════════════════════════════════════════════════════════
# PATTERN 2: Sliding Window Minimum
# ════════════════════════════════════════════════════════════

def sliding_window_min(nums: List[int], k: int) -> List[int]:
    """
    Same idea but keep INCREASING order in deque.
    Remove from back if nums[dq[-1]] >= nums[i].
    """
    dq = deque()
    result = []

    for i, n in enumerate(nums):
        while dq and nums[dq[-1]] >= n:
            dq.pop()
        dq.append(i)
        if dq[0] <= i - k:
            dq.popleft()
        if i >= k - 1:
            result.append(nums[dq[0]])

    return result

print("Sliding min k=3:", sliding_window_min([2,1,5,2,3,2,4,1], 3))


# ════════════════════════════════════════════════════════════
# PATTERN 3: Constrained Sliding Window (variable size)
# ════════════════════════════════════════════════════════════

def longest_subarray_limit(nums: List[int], limit: int) -> int:
    """
    LC 1438: Longest subarray where |max - min| <= limit.
    Use TWO monotonic deques: one for max, one for min.
    Sliding window with two pointers.
    """
    max_dq = deque()   # decreasing → front = max
    min_dq = deque()   # increasing → front = min
    left = 0
    result = 0

    for right, n in enumerate(nums):
        # Maintain decreasing deque for max
        while max_dq and nums[max_dq[-1]] <= n:
            max_dq.pop()
        max_dq.append(right)

        # Maintain increasing deque for min
        while min_dq and nums[min_dq[-1]] >= n:
            min_dq.pop()
        min_dq.append(right)

        # Shrink window if constraint violated
        while nums[max_dq[0]] - nums[min_dq[0]] > limit:
            left += 1
            if max_dq[0] < left: max_dq.popleft()
            if min_dq[0] < left: min_dq.popleft()

        result = max(result, right - left + 1)

    return result

print("Longest subarray limit=2:", longest_subarray_limit([8,2,4,7], 4))  # 2
print("Longest subarray limit=2:", longest_subarray_limit([10,1,2,4,7,2], 5))  # 4


# ════════════════════════════════════════════════════════════
# PATTERN 4: Monotonic Deque for DP Optimization
# ════════════════════════════════════════════════════════════

def max_sum_subarray_no_longer_than_k(nums: List[int], k: int) -> int:
    """
    Max subarray sum with length <= k.
    Use prefix sum + monotonic deque of increasing prefix sums.
    For each i: max(prefix[i] - prefix[j]) where i-j <= k and j < i.
    Keep deque of min prefix[j] for valid j window.
    """
    import math
    prefix = [0] * (len(nums) + 1)
    for i, n in enumerate(nums):
        prefix[i+1] = prefix[i] + n

    result = -math.inf
    dq = deque([0])   # deque of indices with increasing prefix sums

    for i in range(1, len(prefix)):
        # Max sum ending at i = prefix[i] - min prefix[j] in window
        result = max(result, prefix[i] - prefix[dq[0]])
        # Remove front if out of window
        if i - dq[0] >= k:
            dq.popleft()
        # Maintain increasing order (remove larger prefix from back)
        while dq and prefix[dq[-1]] >= prefix[i]:
            dq.pop()
        dq.append(i)

    return result


# ════════════════════════════════════════════════════════════
# PATTERN 5: Jump Game with Deque DP (LC 1696)
# ════════════════════════════════════════════════════════════

def max_result(nums: List[int], k: int) -> int:
    """
    LC 1696: At each step jump 1..k steps. Maximize sum.
    dp[i] = max score to reach i.
    dp[i] = nums[i] + max(dp[i-k..i-1])
    Monotonic deque keeps max of last k dp values.
    """
    n = len(nums)
    dp = [0] * n
    dp[0] = nums[0]
    dq = deque([0])   # indices, dp values decreasing

    for i in range(1, n):
        # Remove front if out of window
        while dq and dq[0] < i - k:
            dq.popleft()
        dp[i] = nums[i] + dp[dq[0]]   # front = max in window
        # Maintain decreasing order
        while dq and dp[dq[-1]] <= dp[i]:
            dq.pop()
        dq.append(i)

    return dp[-1]

print("Max result k=2:", max_result([1,-1,-2,4,-7,3], 2))   # 7
print("Max result k=2:", max_result([10,-5,-2,4,0,3], 3))   # 17


# ════════════════════════════════════════════════════════════
# MONOTONIC STACK vs MONOTONIC QUEUE
# ════════════════════════════════════════════════════════════
"""
MONOTONIC STACK (only pop from top):
  Use for: "next greater/smaller element", "previous greater/smaller"
  Problems: Daily Temperatures, Largest Rectangle in Histogram,
            Trapping Rain Water

MONOTONIC QUEUE/DEQUE (pop from both ends):
  Use for: sliding window max/min
  Problems: Sliding Window Maximum, Longest Subarray with Limit,
            Jump Game VI, Max Value of Equation

KEY DIFFERENCE:
  Stack: elements go in and come out from ONE end only (LIFO).
  Queue: elements enter from back, can be removed from BOTH ends.
         Front removal = "out of window" expiry.
         Back removal = "maintain monotonic order".
"""

# ════════════════════════════════════════════════════════════
# INTERVIEW Q&A
# ════════════════════════════════════════════════════════════
"""
Q1: Why is each element pushed/popped at most once in monotonic deque?
A: Each element is appended to deque exactly once. Each element is also
   removed at most once (either from back when dominated, or from front
   when expired). So total operations = O(2n) = O(n).

Q2: When to use decreasing vs increasing deque?
A: Decreasing deque → front = MAXIMUM (for sliding window max).
   Increasing deque → front = MINIMUM (for sliding window min).
   Rule: remove from back if new element would break monotonic property.

Q3: What do we store in the deque — values or indices?
A: ALWAYS store INDICES. Values can be retrieved from nums[index].
   Storing indices lets you check "is front out of window?" by comparing
   index to current position (dq[0] < i - k).

Q4: How does the two-deque approach for LC 1438 work?
A: Maintain one decreasing deque (for max) and one increasing deque (for min).
   Whenever max - min > limit, shrink window from left.
   Check both deques: remove front if it equals the left boundary being removed.

Q5: How does monotonic deque optimize DP?
A: When dp[i] = f(max or min of dp[j] for j in [i-k, i-1]),
   instead of O(k) per step, maintain a deque of candidate j values.
   New element: pop back if not better than new value.
   Expired element: pop front if j < i-k. O(1) amortized per step.

Q6: Sliding window max using a sorted structure (multiset) — O(n log k)?
A: Yes. Python: use sortedcontainers.SortedList, add/remove in O(log k).
   Deque approach is O(n) which is better. But SortedList gives flexibility
   (e.g., sum of window, not just max).

Q7: Can you find sliding window median using deques?
A: Not easily. Median needs two heaps (max-heap for lower half, min-heap
   for upper half) with lazy deletion. Deque only helps for max/min.

Q8: Real-world use of monotonic queue?
A: Rate limiting (sliding window with max/min thresholds), real-time
   analytics (running max/min over last N events), task scheduling
   (find optimal assignment in O(n) via DP + deque).
"""
