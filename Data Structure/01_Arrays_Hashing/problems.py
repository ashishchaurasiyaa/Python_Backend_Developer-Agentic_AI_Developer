"""
01 — Arrays & Hashing — Problems
==================================
Problems: 15  |  Level: Easy → Medium
Company tags: Google, Amazon, Meta, Microsoft
"""

from collections import Counter, defaultdict
from typing import List, Optional

# ─────────────────────────────────────────────
# P01. Contains Duplicate  [Easy] [LeetCode 217]
# ─────────────────────────────────────────────
"""
Given integer array, return True if any value appears at least twice.
Input: [1,2,3,1]  Output: True
Input: [1,2,3,4]  Output: False
"""
def containsDuplicate(nums: List[int]) -> bool:
    return len(nums) != len(set(nums))

# Alternative with early exit
def containsDuplicate_v2(nums: List[int]) -> bool:
    seen = set()
    for n in nums:
        if n in seen:
            return True
        seen.add(n)
    return False

print("P01:", containsDuplicate([1,2,3,1]))   # True


# ─────────────────────────────────────────────
# P02. Valid Anagram  [Easy] [LeetCode 242]
# ─────────────────────────────────────────────
"""
Given strings s and t, return True if t is an anagram of s.
Input: s="anagram", t="nagaram"  Output: True
"""
def isAnagram(s: str, t: str) -> bool:
    if len(s) != len(t): return False
    return Counter(s) == Counter(t)

# O(1) space alternative (26-letter array)
def isAnagram_v2(s: str, t: str) -> bool:
    if len(s) != len(t): return False
    count = [0] * 26
    for c in s: count[ord(c) - ord('a')] += 1
    for c in t: count[ord(c) - ord('a')] -= 1
    return all(x == 0 for x in count)

print("P02:", isAnagram("anagram", "nagaram"))  # True


# ─────────────────────────────────────────────
# P03. Two Sum  [Easy] [LeetCode 1]
# ─────────────────────────────────────────────
"""
Return indices of two numbers that add up to target.
Input: nums=[2,7,11,15], target=9  Output: [0,1]
"""
def twoSum(nums: List[int], target: int) -> List[int]:
    seen = {}   # value → index
    for i, n in enumerate(nums):
        complement = target - n
        if complement in seen:
            return [seen[complement], i]
        seen[n] = i
    return []

print("P03:", twoSum([2, 7, 11, 15], 9))  # [0, 1]


# ─────────────────────────────────────────────
# P04. Group Anagrams  [Medium] [LeetCode 49]
# ─────────────────────────────────────────────
"""
Group strings that are anagrams of each other.
Input: ["eat","tea","tan","ate","nat","bat"]
Output: [["eat","tea","ate"],["tan","nat"],["bat"]]
"""
def groupAnagrams(strs: List[str]) -> List[List[str]]:
    groups = defaultdict(list)
    for s in strs:
        key = tuple(sorted(s))   # sorted chars = canonical form
        groups[key].append(s)
    return list(groups.values())

print("P04:", groupAnagrams(["eat","tea","tan","ate","nat","bat"]))


# ─────────────────────────────────────────────
# P05. Top K Frequent Elements  [Medium] [LeetCode 347]
# ─────────────────────────────────────────────
"""
Return k most frequent elements.
Input: nums=[1,1,1,2,2,3], k=2  Output: [1, 2]
"""
def topKFrequent(nums: List[int], k: int) -> List[int]:
    # Bucket sort approach: O(n) time
    freq   = Counter(nums)
    bucket = defaultdict(list)   # freq → [nums]
    for num, count in freq.items():
        bucket[count].append(num)

    result = []
    for count in range(len(nums), 0, -1):   # highest freq first
        result.extend(bucket[count])
        if len(result) >= k:
            return result[:k]
    return result

print("P05:", topKFrequent([1,1,1,2,2,3], 2))  # [1, 2]


# ─────────────────────────────────────────────
# P06. Product of Array Except Self  [Medium] [LeetCode 238]
# ─────────────────────────────────────────────
"""
Return array where each element is product of all other elements.
Input: [1,2,3,4]  Output: [24,12,8,6]
No division allowed. O(n) time, O(1) extra space.
"""
def productExceptSelf(nums: List[int]) -> List[int]:
    n      = len(nums)
    result = [1] * n

    # Left pass: result[i] = product of all left of i
    prefix = 1
    for i in range(n):
        result[i] = prefix
        prefix   *= nums[i]

    # Right pass: multiply by product of all right of i
    suffix = 1
    for i in range(n - 1, -1, -1):
        result[i] *= suffix
        suffix    *= nums[i]

    return result

print("P06:", productExceptSelf([1,2,3,4]))  # [24,12,8,6]


# ─────────────────────────────────────────────
# P07. Valid Sudoku  [Medium] [LeetCode 36]
# ─────────────────────────────────────────────
"""
Validate a 9x9 Sudoku board (partial board may be incomplete).
"""
def isValidSudoku(board: List[List[str]]) -> bool:
    rows    = defaultdict(set)
    cols    = defaultdict(set)
    squares = defaultdict(set)   # key: (row//3, col//3)

    for r in range(9):
        for c in range(9):
            val = board[r][c]
            if val == ".":
                continue
            sq = (r // 3, c // 3)
            if val in rows[r] or val in cols[c] or val in squares[sq]:
                return False
            rows[r].add(val)
            cols[c].add(val)
            squares[sq].add(val)
    return True


# ─────────────────────────────────────────────
# P08. Encode and Decode Strings  [Medium]
# ─────────────────────────────────────────────
"""
Design algorithm to encode list of strings to single string and decode back.
"""
class Codec:
    def encode(self, strs: List[str]) -> str:
        # Format: {length}#{string}
        return "".join(f"{len(s)}#{s}" for s in strs)

    def decode(self, s: str) -> List[str]:
        result, i = [], 0
        while i < len(s):
            j = s.index("#", i)         # find next '#'
            length = int(s[i:j])
            result.append(s[j+1 : j+1+length])
            i = j + 1 + length
        return result

codec = Codec()
encoded = codec.encode(["hello", "world", "#test"])
print("P08 encoded:", encoded)
print("P08 decoded:", codec.decode(encoded))


# ─────────────────────────────────────────────
# P09. Longest Consecutive Sequence  [Medium] [LeetCode 128]
# ─────────────────────────────────────────────
"""
Find length of longest consecutive sequence. O(n) time.
Input: [100,4,200,1,3,2]  Output: 4  (sequence: 1,2,3,4)
"""
def longestConsecutive(nums: List[int]) -> int:
    num_set = set(nums)
    longest = 0

    for n in num_set:
        if (n - 1) not in num_set:   # start of a sequence
            length = 1
            while (n + length) in num_set:
                length += 1
            longest = max(longest, length)

    return longest

print("P09:", longestConsecutive([100,4,200,1,3,2]))  # 4


# ─────────────────────────────────────────────
# P10. Subarray Sum Equals K  [Medium] [LeetCode 560]
# ─────────────────────────────────────────────
"""
Find total number of subarrays whose sum equals k.
Input: nums=[1,1,1], k=2  Output: 2
Key insight: prefix_sum[j] - prefix_sum[i] = k  →  prefix[i] = prefix[j] - k
"""
def subarraySum(nums: List[int], k: int) -> int:
    count  = 0
    prefix = 0
    seen   = defaultdict(int)
    seen[0] = 1        # empty prefix

    for n in nums:
        prefix += n
        count  += seen[prefix - k]   # how many times (prefix - k) appeared
        seen[prefix] += 1

    return count

print("P10:", subarraySum([1,1,1], 2))  # 2


# ─────────────────────────────────────────────
# P11. Maximum Subarray (Kadane's)  [Medium] [LeetCode 53]
# ─────────────────────────────────────────────
"""
Find contiguous subarray with largest sum.
Input: [-2,1,-3,4,-1,2,1,-5,4]  Output: 6  ([4,-1,2,1])
"""
def maxSubArray(nums: List[int]) -> int:
    max_sum = nums[0]
    curr    = nums[0]

    for n in nums[1:]:
        curr    = max(n, curr + n)   # restart or extend
        max_sum = max(max_sum, curr)

    return max_sum

print("P11:", maxSubArray([-2,1,-3,4,-1,2,1,-5,4]))  # 6


# ─────────────────────────────────────────────
# P12. Find All Duplicates  [Medium] [LeetCode 442]
# ─────────────────────────────────────────────
"""
Array of n integers where 1 ≤ a[i] ≤ n.
Find all elements that appear twice. O(n) time, O(1) extra space.
"""
def findDuplicates(nums: List[int]) -> List[int]:
    result = []
    for n in nums:
        idx = abs(n) - 1
        if nums[idx] < 0:
            result.append(abs(n))   # already visited
        else:
            nums[idx] = -nums[idx]  # mark visited
    return result

print("P12:", findDuplicates([4,3,2,7,8,2,3,1]))  # [2, 3]


# ─────────────────────────────────────────────
# P13. Majority Element  [Easy] [LeetCode 169]
# ─────────────────────────────────────────────
"""
Find element that appears more than n/2 times. (Boyer-Moore Voting)
Input: [3,2,3]  Output: 3
"""
def majorityElement(nums: List[int]) -> int:
    count, candidate = 0, 0
    for n in nums:
        if count == 0:
            candidate = n
        count += (1 if n == candidate else -1)
    return candidate

print("P13:", majorityElement([3,2,3]))  # 3


# ─────────────────────────────────────────────
# P14. Sort Colors (Dutch Flag)  [Medium] [LeetCode 75]
# ─────────────────────────────────────────────
"""
Sort array with 0,1,2 in-place in O(n), O(1) space.
Input: [2,0,2,1,1,0]  Output: [0,0,1,1,2,2]
"""
def sortColors(nums: List[int]) -> None:
    low, mid, high = 0, 0, len(nums) - 1
    while mid <= high:
        if nums[mid] == 0:
            nums[low], nums[mid] = nums[mid], nums[low]
            low += 1; mid += 1
        elif nums[mid] == 1:
            mid += 1
        else:
            nums[mid], nums[high] = nums[high], nums[mid]
            high -= 1
    print("P14:", nums)

sortColors([2,0,2,1,1,0])  # [0,0,1,1,2,2]


# ─────────────────────────────────────────────
# P15. Range Sum Query (Prefix Sum)  [Easy] [LeetCode 303]
# ─────────────────────────────────────────────
"""
Build prefix sum for O(1) range queries.
"""
class NumArray:
    def __init__(self, nums: List[int]):
        self.prefix = [0] * (len(nums) + 1)
        for i, n in enumerate(nums):
            self.prefix[i+1] = self.prefix[i] + n

    def sumRange(self, left: int, right: int) -> int:
        return self.prefix[right+1] - self.prefix[left]

na = NumArray([-2, 0, 3, -5, 2, -1])
print("P15:", na.sumRange(0,2), na.sumRange(2,5))  # 1, -1


# ─────────────────────────────────────────────
# COMPLEXITY SUMMARY
# ─────────────────────────────────────────────
"""
Problem                      Time     Space   Pattern
─────────────────────────────────────────────────────
Contains Duplicate           O(n)     O(n)    Set
Valid Anagram                O(n)     O(1)    Counter/26-array
Two Sum                      O(n)     O(n)    Hash complement
Group Anagrams               O(n·k)   O(n)    Sorted key hash
Top K Frequent               O(n)     O(n)    Bucket sort
Product Except Self          O(n)     O(1)    Prefix × Suffix
Valid Sudoku                 O(81)    O(1)    3 hash sets
Encode/Decode                O(n)     O(n)    Length prefix
Longest Consecutive          O(n)     O(n)    Set + start detection
Subarray Sum = K             O(n)     O(n)    Prefix sum hash
Max Subarray (Kadane's)      O(n)     O(1)    DP/greedy
Find Duplicates              O(n)     O(1)    Index marking
Majority Element             O(n)     O(1)    Boyer-Moore
Sort Colors                  O(n)     O(1)    Dutch Flag (3-pointer)
Range Sum Query              O(1)     O(n)    Prefix sum
"""
