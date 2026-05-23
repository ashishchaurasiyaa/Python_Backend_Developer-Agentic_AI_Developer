"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DSA — Dynamic Programming: Linear, Grid, Knapsack, String, Sequence
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import bisect


# ─────────────────────────────────────────────────────────────────────────────
# DP APPROACH TEMPLATE
# ─────────────────────────────────────────────────────────────────────────────
# 1. Define state: what does dp[i] or dp[i][j] represent?
# 2. Base case: smallest valid input
# 3. Recurrence relation: how dp[i] depends on previous states
# 4. Build bottom-up (tabulation) — avoid recursion stack overhead
# 5. Return the target state


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 1: LINEAR DP
# ═════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# 1a. CLIMBING STAIRS
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 70
# Time: O(n)   Space: O(1) optimized

def climbStairs(n):
    """
    Count ways to climb n stairs (1 or 2 steps at a time).

    State:    dp[i] = number of ways to reach stair i
    Base:     dp[1] = 1, dp[2] = 2
    Recurrence: dp[i] = dp[i-1] + dp[i-2]
    (same as Fibonacci)
    """
    if n <= 2:
        return n
    prev2, prev1 = 1, 2
    for _ in range(3, n + 1):
        prev2, prev1 = prev1, prev1 + prev2
    return prev1


print("Climbing Stairs(5):", climbStairs(5))   # 8
print("Climbing Stairs(3):", climbStairs(3))   # 3


# ─────────────────────────────────────────────────────────────────────────────
# 1b. HOUSE ROBBER
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 198
# Time: O(n)   Space: O(1)

def rob(nums):
    """
    Max money robbed from houses; cannot rob adjacent houses.

    State:    dp[i] = max money robbing houses 0..i
    Base:     dp[0] = nums[0], dp[1] = max(nums[0], nums[1])
    Recurrence: dp[i] = max(dp[i-1], dp[i-2] + nums[i])
      - Either skip house i (dp[i-1])
      - Or rob house i (dp[i-2] + nums[i])
    """
    if not nums:
        return 0
    if len(nums) == 1:
        return nums[0]

    prev2, prev1 = nums[0], max(nums[0], nums[1])
    for i in range(2, len(nums)):
        prev2, prev1 = prev1, max(prev1, prev2 + nums[i])
    return prev1


print("House Robber:", rob([2, 7, 9, 3, 1]))   # 12  (2 + 9 + 1)
print("House Robber:", rob([1, 2, 3, 1]))       # 4   (1 + 3)


# ─────────────────────────────────────────────────────────────────────────────
# 1c. MAXIMUM SUBARRAY (Kadane's Algorithm)
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 53
# Time: O(n)   Space: O(1)

def maxSubArray(nums):
    """
    Find contiguous subarray with largest sum.

    State:    dp[i] = max subarray sum ending at index i
    Base:     dp[0] = nums[0]
    Recurrence: dp[i] = max(nums[i], dp[i-1] + nums[i])
      - Either start fresh at nums[i]
      - Or extend previous subarray
    Track global max throughout.
    """
    max_sum = curr_sum = nums[0]
    for num in nums[1:]:
        curr_sum = max(num, curr_sum + num)
        max_sum = max(max_sum, curr_sum)
    return max_sum


print("Max Subarray:", maxSubArray([-2, 1, -3, 4, -1, 2, 1, -5, 4]))   # 6


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 2: GRID DP
# ═════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# 2a. UNIQUE PATHS
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 62
# Time: O(m * n)   Space: O(n) — rolling row optimization

def uniquePaths(m, n):
    """
    Count paths from top-left to bottom-right (only right or down moves).

    State:    dp[i][j] = number of unique paths to cell (i, j)
    Base:     dp[0][j] = 1 for all j (top row)
              dp[i][0] = 1 for all i (left col)
    Recurrence: dp[i][j] = dp[i-1][j] + dp[i][j-1]
      (came from above or from the left)
    """
    dp = [1] * n
    for _ in range(1, m):
        for j in range(1, n):
            dp[j] += dp[j - 1]
    return dp[n - 1]


print("Unique Paths(3,7):", uniquePaths(3, 7))   # 28
print("Unique Paths(3,2):", uniquePaths(3, 2))   # 3


# ─────────────────────────────────────────────────────────────────────────────
# 2b. MINIMUM PATH SUM
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 64
# Time: O(m * n)   Space: O(n)

def minPathSum(grid):
    """
    Find path from top-left to bottom-right with minimum sum.

    State:    dp[i][j] = min cost to reach cell (i, j)
    Base:     dp[0][0] = grid[0][0]
    Recurrence: dp[i][j] = grid[i][j] + min(dp[i-1][j], dp[i][j-1])
    """
    m, n = len(grid), len(grid[0])
    dp = grid[0][:]

    # Fill first row
    for j in range(1, n):
        dp[j] = dp[j - 1] + grid[0][j]

    for i in range(1, m):
        dp[0] += grid[i][0]   # first column: only come from above
        for j in range(1, n):
            dp[j] = grid[i][j] + min(dp[j], dp[j - 1])

    return dp[n - 1]


grid_test = [[1,3,1],[1,5,1],[4,2,1]]
print("Min Path Sum:", minPathSum(grid_test))   # 7  (1→3→1→1→1)


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 3: KNAPSACK DP
# ═════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# 3a. 0/1 KNAPSACK
# ─────────────────────────────────────────────────────────────────────────────
# Time: O(n * W)   Space: O(W) with 1D optimization

def knapsack_01(weights, values, W):
    """
    Classic 0/1 knapsack: each item used at most once.

    State:    dp[w] = max value achievable with capacity w
    Base:     dp[0..W] = 0
    Recurrence: dp[w] = max(dp[w], dp[w - weights[i]] + values[i])
    Iterate weights in REVERSE to avoid using item twice.
    """
    dp = [0] * (W + 1)
    for i in range(len(weights)):
        for w in range(W, weights[i] - 1, -1):   # reverse iteration — key!
            dp[w] = max(dp[w], dp[w - weights[i]] + values[i])
    return dp[W]


weights = [2, 3, 4, 5]
values  = [3, 4, 5, 6]
print("0/1 Knapsack (W=5):", knapsack_01(weights, values, 5))    # 7
print("0/1 Knapsack (W=8):", knapsack_01(weights, values, 8))    # 10


# ─────────────────────────────────────────────────────────────────────────────
# 3b. COIN CHANGE (Unbounded Knapsack)
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 322
# Time: O(amount * len(coins))   Space: O(amount)

def coinChange(coins, amount):
    """
    Minimum coins needed to make 'amount' (unlimited coins of each type).

    State:    dp[a] = min coins to make amount a
    Base:     dp[0] = 0
    Recurrence: dp[a] = min(dp[a], dp[a - coin] + 1) for each coin <= a
    Iterate forward (unlike 0/1 knapsack) — items reusable.
    """
    dp = [float('inf')] * (amount + 1)
    dp[0] = 0

    for a in range(1, amount + 1):
        for coin in coins:
            if coin <= a:
                dp[a] = min(dp[a], dp[a - coin] + 1)

    return dp[amount] if dp[amount] != float('inf') else -1


print("Coin Change:", coinChange([1, 5, 6, 9], 11))   # 2  (5+6)
print("Coin Change:", coinChange([2], 3))              # -1


# ─────────────────────────────────────────────────────────────────────────────
# 3c. PARTITION EQUAL SUBSET SUM
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 416
# Time: O(n * sum/2)   Space: O(sum/2)

def canPartition(nums):
    """
    Can array be partitioned into two equal-sum subsets?
    Equivalent to: find subset summing to total_sum / 2.
    Variant of 0/1 knapsack with boolean dp.

    State:    dp[s] = True if subset sum s is achievable
    Base:     dp[0] = True
    Recurrence: dp[s] = dp[s] OR dp[s - num]
    """
    total = sum(nums)
    if total % 2 != 0:
        return False

    target = total // 2
    dp = [False] * (target + 1)
    dp[0] = True

    for num in nums:
        for s in range(target, num - 1, -1):   # reverse — 0/1 knapsack
            dp[s] = dp[s] or dp[s - num]

    return dp[target]


print("Can Partition:", canPartition([1, 5, 11, 5]))   # True  (1+5+5 = 11)
print("Can Partition:", canPartition([1, 2, 3, 5]))    # False


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 4: STRING DP
# ═════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# 4a. LONGEST COMMON SUBSEQUENCE (LCS)
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 1143
# Time: O(m * n)   Space: O(m * n)

def longestCommonSubsequence(text1, text2):
    """
    Length of longest common subsequence of two strings.

    State:    dp[i][j] = LCS length of text1[0..i-1] and text2[0..j-1]
    Base:     dp[0][j] = 0, dp[i][0] = 0
    Recurrence:
        if text1[i-1] == text2[j-1]:  dp[i][j] = dp[i-1][j-1] + 1
        else:                          dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    """
    m, n = len(text1), len(text2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if text1[i - 1] == text2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    return dp[m][n]


print("LCS:", longestCommonSubsequence("abcde", "ace"))     # 3
print("LCS:", longestCommonSubsequence("abc", "abc"))       # 3
print("LCS:", longestCommonSubsequence("abc", "def"))       # 0


# ─────────────────────────────────────────────────────────────────────────────
# 4b. EDIT DISTANCE (Levenshtein Distance)
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 72
# Time: O(m * n)   Space: O(m * n)

def minDistance(word1, word2):
    """
    Minimum edits (insert, delete, replace) to convert word1 to word2.

    State:    dp[i][j] = min edits to convert word1[0..i-1] to word2[0..j-1]
    Base:     dp[i][0] = i  (delete all chars of word1)
              dp[0][j] = j  (insert all chars of word2)
    Recurrence:
        if word1[i-1] == word2[j-1]:
            dp[i][j] = dp[i-1][j-1]          (no operation needed)
        else:
            dp[i][j] = 1 + min(
                dp[i-1][j],    # delete from word1
                dp[i][j-1],    # insert into word1
                dp[i-1][j-1]   # replace in word1
            )
    """
    m, n = len(word1), len(word2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if word1[i - 1] == word2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])

    return dp[m][n]


print("Edit Distance:", minDistance("horse", "ros"))     # 3
print("Edit Distance:", minDistance("intention", "execution"))  # 5


# ─────────────────────────────────────────────────────────────────────────────
# 4c. LONGEST PALINDROMIC SUBSTRING
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 5
# Time: O(n^2)   Space: O(1) — expand around center approach

def longestPalindrome(s):
    """
    Find longest palindromic substring using expand-around-center.
    For each center, expand outward while characters match.
    Check both odd-length (single center) and even-length (two-char center).

    dp approach would be O(n^2) time + O(n^2) space.
    Expand-around-center: O(n^2) time + O(1) space — preferred.
    """
    def expand(left, right):
        while left >= 0 and right < len(s) and s[left] == s[right]:
            left -= 1
            right += 1
        return s[left + 1:right]

    result = ""
    for i in range(len(s)):
        odd  = expand(i, i)       # odd-length palindrome
        even = expand(i, i + 1)   # even-length palindrome
        if len(odd)  > len(result): result = odd
        if len(even) > len(result): result = even

    return result


print("Longest Palindrome:", longestPalindrome("babad"))    # "bab" or "aba"
print("Longest Palindrome:", longestPalindrome("cbbd"))     # "bb"
print("Longest Palindrome:", longestPalindrome("racecar"))  # "racecar"


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 5: SEQUENCE DP — Longest Increasing Subsequence
# ═════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# 5. LONGEST INCREASING SUBSEQUENCE (LIS)
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 300

# --- O(n^2) DP solution ---
def lis_dp(nums):
    """
    State:    dp[i] = length of LIS ending at index i
    Base:     dp[i] = 1 for all i (each element is an LIS of length 1)
    Recurrence: dp[i] = max(dp[j] + 1) for all j < i where nums[j] < nums[i]
    Time: O(n^2)   Space: O(n)
    """
    n = len(nums)
    dp = [1] * n
    for i in range(1, n):
        for j in range(i):
            if nums[j] < nums[i]:
                dp[i] = max(dp[i], dp[j] + 1)
    return max(dp)


# --- O(n log n) solution using patience sorting + bisect ---
def lis_nlogn(nums):
    """
    Maintain a 'tails' array where tails[i] = smallest tail element
    of all increasing subsequences of length i+1.

    For each num:
    - If num > all tails: extend the longest subsequence
    - Else: replace the first tail >= num (using bisect_left)

    This maintains the invariant that 'tails' is always sorted.
    Time: O(n log n)   Space: O(n)
    """
    tails = []
    for num in nums:
        pos = bisect.bisect_left(tails, num)
        if pos == len(tails):
            tails.append(num)
        else:
            tails[pos] = num
    return len(tails)


print("LIS O(n^2):", lis_dp([10, 9, 2, 5, 3, 7, 101, 18]))     # 4
print("LIS O(nlogn):", lis_nlogn([10, 9, 2, 5, 3, 7, 101, 18])) # 4
print("LIS O(nlogn):", lis_nlogn([0, 1, 0, 3, 2, 3]))           # 4


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 6: INTERVAL DP — Burst Balloons (Concept)
# ═════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# 6. BURST BALLOONS
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 312
# Time: O(n^3)   Space: O(n^2)

def maxCoins(nums):
    """
    Burst all balloons to maximize total coins.
    Coins from bursting balloon i = nums[left] * nums[i] * nums[right]
    where left, right are the nearest unbursted neighbors.

    Key insight: Instead of "which balloon to burst first",
    think "which balloon to burst LAST in range [left, right]".

    State:    dp[l][r] = max coins from bursting all balloons in (l, r)
              (exclusive boundaries — l and r are NOT burst in this subproblem)
    Base:     dp[l][r] = 0 when no balloons between l and r
    Recurrence:
        For each k in (l, r) as the LAST balloon burst:
        dp[l][r] = max(dp[l][r],
                       dp[l][k] + nums[l]*nums[k]*nums[r] + dp[k][r])

    Pad nums with 1s on both sides to handle boundary conditions.
    """
    nums = [1] + nums + [1]
    n = len(nums)
    dp = [[0] * n for _ in range(n)]

    # length of interval (number of elements between l and r)
    for length in range(2, n):
        for l in range(0, n - length):
            r = l + length
            for k in range(l + 1, r):
                coins = nums[l] * nums[k] * nums[r]
                dp[l][r] = max(dp[l][r], dp[l][k] + coins + dp[k][r])

    return dp[0][n - 1]


print("Burst Balloons:", maxCoins([3, 1, 5, 8]))   # 167
print("Burst Balloons:", maxCoins([1, 5]))          # 10


# ─────────────────────────────────────────────────────────────────────────────
# COMPLEXITY SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
"""
Problem                         Time            Space       Notes
──────────────────────────────────────────────────────────────────────────────
Climbing Stairs                 O(n)            O(1)        Fibonacci variant
House Robber                    O(n)            O(1)
Maximum Subarray (Kadane's)     O(n)            O(1)
Unique Paths                    O(m*n)          O(n)        Rolling row
Minimum Path Sum                O(m*n)          O(n)        Rolling row
0/1 Knapsack                    O(n*W)          O(W)        Reverse loop
Coin Change (unbounded)         O(amount*coins) O(amount)   Forward loop
Partition Equal Subset          O(n*sum)        O(sum)
LCS                             O(m*n)          O(m*n)
Edit Distance                   O(m*n)          O(m*n)
Longest Palindrome (expand)     O(n^2)          O(1)
LIS (DP)                        O(n^2)          O(n)
LIS (bisect)                    O(n log n)      O(n)        Patience sort
Burst Balloons                  O(n^3)          O(n^2)      Interval DP
──────────────────────────────────────────────────────────────────────────────
KEY INSIGHT: 0/1 knapsack → reverse inner loop (each item used once)
             Unbounded knapsack → forward inner loop (item reusable)
"""
