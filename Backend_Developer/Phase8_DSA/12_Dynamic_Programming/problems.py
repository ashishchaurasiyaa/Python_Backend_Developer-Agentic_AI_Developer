"""
╔══════════════════════════════════════════════════════════════════╗
║         DYNAMIC PROGRAMMING — 15 LeetCode-Style Problems         ║
╚══════════════════════════════════════════════════════════════════╝
"""

from typing import List
from functools import lru_cache
import bisect

# ══════════════════════════════════════════════════════════════════
# Problem 1: Climbing Stairs (LC 70)
# ══════════════════════════════════════════════════════════════════
def climbStairs(n: int) -> int:
    """
    Reach top of n steps. Each time you can climb 1 or 2 steps.
    How many distinct ways?

    dp[i] = dp[i-1] + dp[i-2]  (same as Fibonacci)

    Example: n=3 → 3  (1+1+1, 1+2, 2+1)
    """
    if n <= 2: return n
    a, b = 1, 2
    for _ in range(3, n+1):
        a, b = b, a + b
    return b

print("=== Climbing Stairs ===")
print(climbStairs(3))  # 3
print(climbStairs(5))  # 8
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 2: House Robber (LC 198)
# ══════════════════════════════════════════════════════════════════
def rob(nums: List[int]) -> int:
    """
    Rob houses in a row. Can't rob adjacent houses. Maximize money.
    dp[i] = max(dp[i-1], dp[i-2] + nums[i])

    Example: [1,2,3,1] → 4  (rob 1 and 3)
             [2,7,9,3,1] → 12 (rob 2, 9, 1)
    """
    if not nums: return 0
    prev2, prev1 = 0, 0
    for num in nums:
        curr = max(prev1, prev2 + num)
        prev2, prev1 = prev1, curr
    return prev1

print("\n=== House Robber ===")
print(rob([1,2,3,1]))    # 4
print(rob([2,7,9,3,1]))  # 12
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 3: House Robber II (LC 213)
# ══════════════════════════════════════════════════════════════════
def robII(nums: List[int]) -> int:
    """
    Houses arranged in a CIRCLE (first and last are adjacent).
    Can't rob both first and last.

    Approach: Run house robber twice:
    - Excluding last house: nums[0..n-2]
    - Excluding first house: nums[1..n-1]
    Take the maximum.

    Example: [2,3,2] → 3  [1,2,3,1] → 4
    """
    def rob_line(houses):
        prev2, prev1 = 0, 0
        for h in houses:
            curr = max(prev1, prev2 + h)
            prev2, prev1 = prev1, curr
        return prev1

    if len(nums) == 1: return nums[0]
    return max(rob_line(nums[:-1]), rob_line(nums[1:]))

print("\n=== House Robber II ===")
print(robII([2,3,2]))   # 3
print(robII([1,2,3,1])) # 4
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 4: Longest Palindromic Substring (LC 5)
# ══════════════════════════════════════════════════════════════════
def longestPalindrome(s: str) -> str:
    """
    Find the longest palindromic substring.

    Approach: Expand Around Center. For each center (n centers for odd,
    n-1 for even), expand outward while characters match.

    Example: "babad" → "bab"  "cbbd" → "bb"
    """
    result = ""
    def expand(lo, hi):
        while lo >= 0 and hi < len(s) and s[lo] == s[hi]:
            lo -= 1; hi += 1
        return s[lo+1:hi]
    for i in range(len(s)):
        odd = expand(i, i)
        even = expand(i, i+1)
        if len(odd) > len(result): result = odd
        if len(even) > len(result): result = even
    return result

print("\n=== Longest Palindromic Substring ===")
print(longestPalindrome("babad"))  # "bab"
print(longestPalindrome("cbbd"))   # "bb"
# Time: O(n²) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 5: Palindromic Substrings (LC 647)
# ══════════════════════════════════════════════════════════════════
def countSubstrings(s: str) -> int:
    """
    Count all palindromic substrings.

    Approach: Expand around center, count each valid expansion.

    Example: "abc" → 3  "aaa" → 6
    """
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

print("\n=== Palindromic Substrings ===")
print(countSubstrings("abc"))  # 3
print(countSubstrings("aaa"))  # 6
# Time: O(n²) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 6: Decode Ways (LC 91)
# ══════════════════════════════════════════════════════════════════
def numDecodings(s: str) -> int:
    """
    'A'=1,...,'Z'=26. Count ways to decode digit string.
    Leading zeros are invalid.

    dp[i] = ways to decode s[:i]
    - Single digit: dp[i] += dp[i-1] if s[i-1] != '0'
    - Two digits: dp[i] += dp[i-2] if 10 <= int(s[i-2:i]) <= 26

    Example: "12" → 2 ("AB" or "L")  "226" → 3  "06" → 0
    """
    if not s or s[0] == '0': return 0
    n = len(s)
    prev2, prev1 = 1, 1

    for i in range(1, n):
        curr = 0
        if s[i] != '0':
            curr += prev1
        two_digit = int(s[i-1:i+1])
        if 10 <= two_digit <= 26:
            curr += prev2
        prev2, prev1 = prev1, curr

    return prev1

print("\n=== Decode Ways ===")
print(numDecodings("12"))   # 2
print(numDecodings("226"))  # 3
print(numDecodings("06"))   # 0
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 7: Coin Change (LC 322)
# ══════════════════════════════════════════════════════════════════
def coinChange(coins: List[int], amount: int) -> int:
    """
    Find minimum number of coins to make amount. Unlimited coin supply.

    dp[i] = min coins to make amount i
    Transition: dp[i] = min(dp[i - c] + 1) for each coin c

    Example: coins=[1,5,11], amount=15 → 3 (5+5+5)
             coins=[2], amount=3 → -1
    """
    dp = [float('inf')] * (amount + 1)
    dp[0] = 0
    for i in range(1, amount + 1):
        for coin in coins:
            if coin <= i:
                dp[i] = min(dp[i], dp[i - coin] + 1)
    return dp[amount] if dp[amount] != float('inf') else -1

print("\n=== Coin Change ===")
print(coinChange([1,5,11], 15))  # 3
print(coinChange([1,2,5], 11))   # 3
print(coinChange([2], 3))        # -1
# Time: O(n * amount) | Space: O(amount)

# ══════════════════════════════════════════════════════════════════
# Problem 8: Maximum Product Subarray (LC 152)
# ══════════════════════════════════════════════════════════════════
def maxProduct(nums: List[int]) -> int:
    """
    Find the contiguous subarray with the largest product.

    Key insight: Negative * negative = positive.
    Track BOTH max and min product ending at current position.
    On negative number, swap max and min.

    Example: [2,3,-2,4] → 6  [-2,0,-1] → 0
    """
    max_prod = min_prod = result = nums[0]
    for num in nums[1:]:
        candidates = (num, max_prod * num, min_prod * num)
        max_prod = max(candidates)
        min_prod = min(candidates)
        result = max(result, max_prod)
    return result

print("\n=== Maximum Product Subarray ===")
print(maxProduct([2,3,-2,4]))  # 6
print(maxProduct([-2,0,-1]))   # 0
print(maxProduct([-2,3,-4]))   # 24
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 9: Word Break (LC 139)
# ══════════════════════════════════════════════════════════════════
def wordBreak(s: str, wordDict: List[str]) -> bool:
    """
    Can s be segmented into words from wordDict?

    dp[i] = True if s[:i] can be segmented.
    Transition: dp[i] = True if any dp[j] is True and s[j:i] in wordDict.

    Example: s="leetcode", wordDict=["leet","code"] → True
             s="applepenapple", wordDict=["apple","pen"] → True
             s="catsandog", wordDict=["cats","dog","sand","and","cat"] → False
    """
    word_set = set(wordDict)
    n = len(s)
    dp = [False] * (n + 1)
    dp[0] = True  # empty string is always segmentable

    for i in range(1, n + 1):
        for j in range(i):
            if dp[j] and s[j:i] in word_set:
                dp[i] = True
                break

    return dp[n]

print("\n=== Word Break ===")
print(wordBreak("leetcode", ["leet","code"]))                                   # True
print(wordBreak("applepenapple", ["apple","pen"]))                              # True
print(wordBreak("catsandog", ["cats","dog","sand","and","cat"]))                # False
# Time: O(n³) — O(n²) states * O(n) substring | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 10: Longest Increasing Subsequence (LC 300)
# ══════════════════════════════════════════════════════════════════
def lengthOfLIS(nums: List[int]) -> int:
    """
    Find length of longest strictly increasing subsequence.

    Approach: O(n log n) patience sorting.
    Maintain 'tails' array: tails[i] = smallest tail of LIS of length i+1.
    Binary search to find where to place each number.

    Example: [10,9,2,5,3,7,101,18] → 4 ([2,3,7,101])
    """
    tails = []
    for num in nums:
        pos = bisect.bisect_left(tails, num)
        if pos == len(tails):
            tails.append(num)
        else:
            tails[pos] = num
    return len(tails)

print("\n=== Longest Increasing Subsequence ===")
print(lengthOfLIS([10,9,2,5,3,7,101,18]))  # 4
print(lengthOfLIS([0,1,0,3,2,3]))          # 4
print(lengthOfLIS([7,7,7,7,7]))            # 1
# Time: O(n log n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 11: Unique Paths (LC 62)
# ══════════════════════════════════════════════════════════════════
def uniquePaths(m: int, n: int) -> int:
    """
    A robot on m×n grid. Can only move right or down.
    Count unique paths from top-left to bottom-right.

    dp[i][j] = paths to reach (i,j) = dp[i-1][j] + dp[i][j-1]
    Space optimized: use single row.

    Example: m=3, n=7 → 28   m=3, n=2 → 3
    """
    dp = [1] * n
    for i in range(1, m):
        for j in range(1, n):
            dp[j] += dp[j-1]
    return dp[n-1]

print("\n=== Unique Paths ===")
print(uniquePaths(3, 7))  # 28
print(uniquePaths(3, 2))  # 3
# Time: O(m*n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 12: Jump Game (LC 55)
# ══════════════════════════════════════════════════════════════════
def canJump(nums: List[int]) -> bool:
    """
    Each element = max jump distance. Can you reach the last index?

    Approach: Greedy — track maximum reachable index.
    At each i, update max_reach = max(max_reach, i + nums[i]).
    If i > max_reach, can't reach here.

    Example: [2,3,1,1,4] → True  [3,2,1,0,4] → False
    """
    max_reach = 0
    for i, jump in enumerate(nums):
        if i > max_reach:
            return False
        max_reach = max(max_reach, i + jump)
    return True

print("\n=== Jump Game ===")
print(canJump([2,3,1,1,4]))  # True
print(canJump([3,2,1,0,4]))  # False
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 13: 0/1 Knapsack (Classic)
# ══════════════════════════════════════════════════════════════════
def knapsack(weights: List[int], values: List[int], capacity: int) -> int:
    """
    Classic 0/1 Knapsack: maximize value with weight <= capacity.
    Each item can be included at most once.

    dp[w] = max value achievable with capacity w.
    Iterate weights in REVERSE to ensure each item used at most once.

    Example: weights=[1,3,4,5], values=[1,4,5,7], capacity=7 → 9
    """
    dp = [0] * (capacity + 1)
    for i in range(len(weights)):
        for w in range(capacity, weights[i]-1, -1):  # reverse!
            dp[w] = max(dp[w], dp[w - weights[i]] + values[i])
    return dp[capacity]

print("\n=== 0/1 Knapsack ===")
print(knapsack([1,3,4,5], [1,4,5,7], 7))  # 9
print(knapsack([2,3,4,5], [3,4,5,6], 8))  # 10
# Time: O(n * W) | Space: O(W)

# ══════════════════════════════════════════════════════════════════
# Problem 14: Longest Common Subsequence (LC 1143)
# ══════════════════════════════════════════════════════════════════
def longestCommonSubsequence(text1: str, text2: str) -> int:
    """
    Find length of longest common subsequence.

    dp[i][j] = LCS of text1[:i] and text2[:j]
    if text1[i-1] == text2[j-1]: dp[i][j] = dp[i-1][j-1] + 1
    else: dp[i][j] = max(dp[i-1][j], dp[i][j-1])

    Example: "abcde","ace" → 3  "abc","abc" → 3  "abc","def" → 0
    """
    m, n = len(text1), len(text2)
    # Space optimized: only keep prev row
    prev = [0] * (n + 1)
    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if text1[i-1] == text2[j-1]:
                curr[j] = prev[j-1] + 1
            else:
                curr[j] = max(prev[j], curr[j-1])
        prev = curr
    return prev[n]

print("\n=== Longest Common Subsequence ===")
print(longestCommonSubsequence("abcde","ace"))  # 3
print(longestCommonSubsequence("abc","abc"))    # 3
print(longestCommonSubsequence("abc","def"))    # 0
# Time: O(m*n) | Space: O(n) optimized

# ══════════════════════════════════════════════════════════════════
# Problem 15: Edit Distance (LC 72)
# ══════════════════════════════════════════════════════════════════
def minDistance(word1: str, word2: str) -> int:
    """
    Minimum operations (insert, delete, replace) to convert word1 to word2.

    dp[i][j] = min ops to convert word1[:i] to word2[:j]
    if word1[i-1] == word2[j-1]: dp[i][j] = dp[i-1][j-1]  (no op)
    else: dp[i][j] = 1 + min(
        dp[i-1][j-1],  # replace
        dp[i-1][j],    # delete from word1
        dp[i][j-1]     # insert into word1
    )

    Example: "horse","ros" → 3  "intention","execution" → 5
    """
    m, n = len(word1), len(word2)
    prev = list(range(n + 1))  # base: converting "" to word2[:j] = j insertions

    for i in range(1, m + 1):
        curr = [i] + [0] * n  # base: converting word1[:i] to "" = i deletions
        for j in range(1, n + 1):
            if word1[i-1] == word2[j-1]:
                curr[j] = prev[j-1]
            else:
                curr[j] = 1 + min(prev[j-1], prev[j], curr[j-1])
        prev = curr

    return prev[n]

print("\n=== Edit Distance ===")
print(minDistance("horse","ros"))         # 3
print(minDistance("intention","execution")) # 5
print(minDistance("",""))                 # 0
# Time: O(m*n) | Space: O(n) optimized

print("\n✓ All 15 Dynamic Programming problems solved!")
