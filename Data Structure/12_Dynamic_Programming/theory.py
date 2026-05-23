"""
╔══════════════════════════════════════════════════════════════════╗
║           DYNAMIC PROGRAMMING — Complete Theory Guide            ║
╚══════════════════════════════════════════════════════════════════╝

WHAT IS DYNAMIC PROGRAMMING?
─────────────────────────────
DP is an optimization technique for problems with:
  1. OVERLAPPING SUBPROBLEMS — same subproblem solved multiple times
  2. OPTIMAL SUBSTRUCTURE — optimal solution built from optimal subsolutions

DP PHILOSOPHY:
  "Solve each subproblem once, store the result, reuse it."

TWO APPROACHES:
  Top-Down (Memoization): Recursive + cache results. Natural to think.
  Bottom-Up (Tabulation): Iterative, fill table from base case up. Usually faster.

WHEN TO USE DP?
  - "Count the number of ways"
  - "Find min/max cost/value"
  - "Is it possible?"
  - Overlapping recursive calls (draw recursion tree, see repeated work)
  - Future decisions depend on current choice, not on how you got here

DP PROBLEM-SOLVING FRAMEWORK:
  1. Define STATE: what information do we need at each step?
  2. Define TRANSITION: how do we get to state i from previous states?
  3. Define BASE CASE: what are the smallest, known subproblems?
  4. Define ANSWER: what state/value gives the final answer?

COMPLEXITY TABLE
─────────────────────────────────────────────────────────────────
Pattern           Time        Space    Example
─────────────────────────────────────────────────────────────────
1D DP             O(n)        O(n)     Fibonacci, Climbing Stairs
1D DP optimized   O(n)        O(1)     (only prev 2 states needed)
2D DP             O(m*n)      O(m*n)   LCS, Edit Distance
2D DP optimized   O(m*n)      O(n)     (only prev row needed)
0/1 Knapsack      O(n*W)      O(n*W)   exact or O(W) optimized
Bitmask DP        O(2^n * n)  O(2^n)   TSP
─────────────────────────────────────────────────────────────────
"""

from typing import List
from functools import lru_cache

# ─────────────────────────────────────────────
# 1. TOP-DOWN vs BOTTOM-UP
# ─────────────────────────────────────────────
print("=" * 60)
print("1. TOP-DOWN (Memoization) vs BOTTOM-UP (Tabulation)")
print("=" * 60)

# Fibonacci — both approaches
def fib_top_down(n: int) -> int:
    """Top-down: recursive with memoization."""
    @lru_cache(maxsize=None)
    def dp(i):
        if i <= 1: return i
        return dp(i-1) + dp(i-2)
    return dp(n)

def fib_bottom_up(n: int) -> int:
    """Bottom-up: iterative tabulation."""
    if n <= 1: return n
    dp = [0] * (n + 1)
    dp[0], dp[1] = 0, 1
    for i in range(2, n + 1):
        dp[i] = dp[i-1] + dp[i-2]
    return dp[n]

def fib_optimized(n: int) -> int:
    """Optimized: O(1) space — only need last two values."""
    if n <= 1: return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

print(f"fib(10) top-down:  {fib_top_down(10)}")   # 55
print(f"fib(10) bottom-up: {fib_bottom_up(10)}")   # 55
print(f"fib(10) optimized: {fib_optimized(10)}")   # 55

# ─────────────────────────────────────────────
# 2. PATTERN 1: 1D Fibonacci-Style DP
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("2. PATTERN 1: 1D Fibonacci-Style DP")
print("=" * 60)

"""
Problems: Climbing Stairs, House Robber, Decode Ways

STATE: dp[i] = answer for prefix/subproblem of size i
TRANSITION: dp[i] = f(dp[i-1], dp[i-2], ...)
BASE CASE: dp[0] and dp[1] are known
"""

def climbing_stairs(n: int) -> int:
    """
    Reach top in n steps. Can climb 1 or 2 steps at a time.
    dp[i] = ways to reach step i = dp[i-1] + dp[i-2]
    """
    if n <= 2: return n
    a, b = 1, 2
    for _ in range(3, n+1):
        a, b = b, a + b
    return b

print(f"Climb 5 stairs: {climbing_stairs(5)}")  # 8

def house_robber(nums: List[int]) -> int:
    """
    Rob houses (can't rob adjacent). Max profit.
    dp[i] = max(dp[i-1], dp[i-2] + nums[i])
    """
    if not nums: return 0
    if len(nums) == 1: return nums[0]
    prev2, prev1 = 0, nums[0]
    for i in range(1, len(nums)):
        curr = max(prev1, prev2 + nums[i])
        prev2, prev1 = prev1, curr
    return prev1

print(f"Rob [2,7,9,3,1]: {house_robber([2,7,9,3,1])}")  # 12

# ─────────────────────────────────────────────
# 3. PATTERN 2: 0/1 Knapsack
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("3. PATTERN 2: 0/1 Knapsack")
print("=" * 60)

"""
Given items with weights and values, fill knapsack of capacity W.
Each item can be used AT MOST ONCE.

STATE: dp[i][w] = max value using first i items with capacity w
TRANSITION:
  - Don't take item i: dp[i][w] = dp[i-1][w]
  - Take item i (if weight[i] <= w): dp[i][w] = dp[i-1][w-weight[i]] + value[i]
  dp[i][w] = max of the two
BASE CASE: dp[0][w] = 0 for all w (no items, no value)
"""

def knapsack_01(weights: List[int], values: List[int], capacity: int) -> int:
    n = len(weights)
    dp = [[0] * (capacity + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for w in range(capacity + 1):
            dp[i][w] = dp[i-1][w]  # don't take item i
            if weights[i-1] <= w:
                dp[i][w] = max(dp[i][w], dp[i-1][w-weights[i-1]] + values[i-1])
    return dp[n][capacity]

# Space-optimized 0/1 Knapsack (1D dp, iterate W in REVERSE)
def knapsack_01_optimized(weights, values, capacity):
    dp = [0] * (capacity + 1)
    for i in range(len(weights)):
        for w in range(capacity, weights[i] - 1, -1):  # must go backward!
            dp[w] = max(dp[w], dp[w - weights[i]] + values[i])
    return dp[capacity]

weights = [2, 3, 4, 5]
values  = [3, 4, 5, 6]
W = 8
print(f"0/1 Knapsack max value: {knapsack_01(weights, values, W)}")           # 10
print(f"0/1 Knapsack optimized: {knapsack_01_optimized(weights, values, W)}") # 10

# ─────────────────────────────────────────────
# 4. PATTERN 3: Unbounded Knapsack
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("4. PATTERN 3: Unbounded Knapsack (can reuse items)")
print("=" * 60)

"""
Same as 0/1 Knapsack but each item can be used UNLIMITED times.
TRANSITION: dp[w] = max(dp[w], dp[w - weight[i]] + value[i])
KEY DIFFERENCE: Iterate W FORWARD (allows reuse of same item).
"""

def coin_change(coins: List[int], amount: int) -> int:
    """
    Min coins to make amount. Unbounded — can reuse coins.
    dp[i] = min coins to make amount i
    """
    dp = [float('inf')] * (amount + 1)
    dp[0] = 0
    for i in range(1, amount + 1):
        for coin in coins:
            if coin <= i:
                dp[i] = min(dp[i], dp[i - coin] + 1)
    return dp[amount] if dp[amount] != float('inf') else -1

print(f"Min coins for 11 with [1,5,6,9]: {coin_change([1,5,6,9], 11)}")  # 2

# ─────────────────────────────────────────────
# 5. PATTERN 4: LCS (Longest Common Subsequence)
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("5. PATTERN 4: LCS — 2D DP")
print("=" * 60)

"""
LCS of strings s1 and s2:
STATE: dp[i][j] = LCS length of s1[:i] and s2[:j]
TRANSITION:
  if s1[i-1] == s2[j-1]: dp[i][j] = dp[i-1][j-1] + 1
  else: dp[i][j] = max(dp[i-1][j], dp[i][j-1])
BASE CASE: dp[0][j] = dp[i][0] = 0
"""

def lcs(s1: str, s2: str) -> int:
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i-1] == s2[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    return dp[m][n]

print(f"LCS('abcde','ace'): {lcs('abcde','ace')}")  # 3

# ─────────────────────────────────────────────
# 6. PATTERN 5: LIS (Longest Increasing Subsequence)
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("6. PATTERN 5: LIS — O(n log n)")
print("=" * 60)

"""
LIS of array nums:
STATE: dp[i] = length of LIS ending at index i
TRANSITION: dp[i] = max(dp[j] + 1) for all j < i where nums[j] < nums[i]
BASE CASE: dp[i] = 1 (just the element itself)
Answer: max(dp)

O(n log n) using patience sorting:
Maintain a 'tails' array where tails[i] = smallest tail of increasing
subsequence of length i+1. Binary search to find replacement position.
"""

def lis_dp(nums: List[int]) -> int:
    """O(n²) DP solution."""
    n = len(nums)
    dp = [1] * n
    for i in range(1, n):
        for j in range(i):
            if nums[j] < nums[i]:
                dp[i] = max(dp[i], dp[j] + 1)
    return max(dp)

import bisect
def lis_nlogn(nums: List[int]) -> int:
    """O(n log n) patience sorting solution."""
    tails = []
    for num in nums:
        pos = bisect.bisect_left(tails, num)
        if pos == len(tails):
            tails.append(num)
        else:
            tails[pos] = num
    return len(tails)

nums = [10, 9, 2, 5, 3, 7, 101, 18]
print(f"LIS of {nums}: {lis_dp(nums)}")      # 4
print(f"LIS O(nlogn): {lis_nlogn(nums)}")    # 4

# ─────────────────────────────────────────────
# 7. PATTERN 6: Palindrome DP
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("7. PATTERN 6: Palindrome DP")
print("=" * 60)

"""
Longest Palindromic Substring:
Approach 1: Expand Around Center — O(n²) time, O(1) space.
Approach 2: 2D DP — dp[i][j] = is s[i:j+1] a palindrome?
  s[i:j+1] is palindrome iff s[i]==s[j] AND s[i+1:j] is palindrome.
"""

def longest_palindrome_expand(s: str) -> str:
    """Expand around center — O(n²) time, O(1) space."""
    result = ""
    def expand(lo, hi):
        while lo >= 0 and hi < len(s) and s[lo] == s[hi]:
            lo -= 1; hi += 1
        return s[lo+1:hi]  # shrink back after overshoot
    for i in range(len(s)):
        odd = expand(i, i)      # odd length palindromes
        even = expand(i, i+1)   # even length palindromes
        if len(odd) > len(result): result = odd
        if len(even) > len(result): result = even
    return result

print(f"Longest palindrome in 'babad': {longest_palindrome_expand('babad')}")  # "bab" or "aba"
print(f"Longest palindrome in 'cbbd': {longest_palindrome_expand('cbbd')}")    # "bb"

# Count palindromic substrings
def count_palindromes(s: str) -> int:
    """Count all palindromic substrings."""
    count = 0
    def expand(lo, hi):
        nonlocal count
        while lo >= 0 and hi < len(s) and s[lo] == s[hi]:
            count += 1
            lo -= 1; hi += 1
    for i in range(len(s)):
        expand(i, i)    # odd
        expand(i, i+1)  # even
    return count

print(f"Count palindromes in 'abc': {count_palindromes('abc')}")    # 3
print(f"Count palindromes in 'aaa': {count_palindromes('aaa')}")    # 6

# ─────────────────────────────────────────────
# 8. INTERVIEW Q&A
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("INTERVIEW Q&A")
print("=" * 60)

qa = """
Q1: What's the difference between memoization and tabulation?
A1: Memoization (top-down): recursive, only computes subproblems needed.
    Tabulation (bottom-up): iterative, computes ALL subproblems in order.
    Tabulation is usually faster (no function call overhead) and avoids
    stack overflow. Memoization is more natural to code.

Q2: How do you identify if a problem can be solved with DP?
A2: Clues: "count ways", "minimum/maximum", "is it possible",
    "optimal" + "substructure". Draw the recursion tree — if same
    calls appear multiple times → DP.

Q3: How do you define the DP state?
A3: State = the minimal information needed to describe a subproblem.
    Usually: position, amount/capacity remaining, flags for constraints.
    Start with the recursive function signature — the parameters ARE the state.

Q4: Why does 0/1 Knapsack iterate W in reverse (space optimization)?
A4: In the 1D optimization, dp[w] represents "using items seen so far".
    Iterating forward would allow using the SAME item multiple times
    (because dp[w-weight] would already include the current item).
    Reverse iteration ensures dp[w-weight] still refers to BEFORE the current item.

Q5: What is the difference between LCS and LIS?
A5: LCS: between TWO sequences, subsequence from both. 2D DP O(mn).
    LIS: within ONE sequence, longest strictly increasing subsequence.
    1D DP O(n²) or O(n log n) with patience sorting.

Q6: What is the space optimization for 2D DP?
A6: When dp[i][j] only depends on dp[i-1][...] (previous row),
    use two 1D arrays (prev and curr) or just one (iterate in right direction).
    This reduces space from O(m*n) to O(n).

Q7: When would you use bitmask DP?
A7: When n is small (≤ 20) and you need to track which subset of n items
    has been "used". State = bitmask representing used items.
    Example: Traveling Salesman Problem, minimum cost to visit all nodes.
"""
print(qa)
