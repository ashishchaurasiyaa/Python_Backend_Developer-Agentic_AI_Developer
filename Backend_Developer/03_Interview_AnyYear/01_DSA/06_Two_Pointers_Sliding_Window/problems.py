"""
╔══════════════════════════════════════════════════════════════════╗
║     TWO POINTERS & SLIDING WINDOW — 16 LeetCode-Style Problems   ║
╚══════════════════════════════════════════════════════════════════╝
"""

from typing import List
from collections import Counter, defaultdict

# ══════════════════════════════════════════════════════════════════
# Problem 1: Two Sum II - Input Array is Sorted (LC 167)
# ══════════════════════════════════════════════════════════════════
def twoSum(numbers: List[int], target: int) -> List[int]:
    """
    Given a 1-indexed sorted array, find two numbers summing to target.
    Return their 1-indexed positions.

    Approach: Two pointers from both ends. If sum < target → move left pointer
    right. If sum > target → move right pointer left.

    Example:
      [2,7,11,15], target=9 → [1,2]
      [2,3,4], target=6 → [1,3]
    """
    lo, hi = 0, len(numbers) - 1
    while lo < hi:
        s = numbers[lo] + numbers[hi]
        if s == target:
            return [lo + 1, hi + 1]
        elif s < target:
            lo += 1
        else:
            hi -= 1
    return []

print("=== Two Sum II ===")
print(twoSum([2,7,11,15], 9))   # [1,2]
print(twoSum([2,3,4], 6))       # [1,3]
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 2: 3Sum (LC 15)
# ══════════════════════════════════════════════════════════════════
def threeSum(nums: List[int]) -> List[List[int]]:
    """
    Find all unique triplets in nums that sum to zero.

    Approach: Sort. For each element nums[i], use two pointers for
    the remaining pair. Skip duplicates at each pointer.

    Example:
      [-1,0,1,2,-1,-4] → [[-1,-1,2],[-1,0,1]]
      [0,1,1] → []
      [0,0,0] → [[0,0,0]]
    """
    nums.sort()
    result = []
    for i in range(len(nums) - 2):
        if nums[i] > 0:
            break  # all positive, can't sum to 0
        if i > 0 and nums[i] == nums[i-1]:
            continue  # skip duplicate pivot
        lo, hi = i + 1, len(nums) - 1
        while lo < hi:
            s = nums[i] + nums[lo] + nums[hi]
            if s == 0:
                result.append([nums[i], nums[lo], nums[hi]])
                while lo < hi and nums[lo] == nums[lo+1]: lo += 1
                while lo < hi and nums[hi] == nums[hi-1]: hi -= 1
                lo += 1; hi -= 1
            elif s < 0:
                lo += 1
            else:
                hi -= 1
    return result

print("\n=== 3Sum ===")
print(threeSum([-1,0,1,2,-1,-4]))  # [[-1,-1,2],[-1,0,1]]
print(threeSum([0,1,1]))           # []
print(threeSum([0,0,0]))           # [[0,0,0]]
# Time: O(n²) | Space: O(1) excl. output

# ══════════════════════════════════════════════════════════════════
# Problem 3: Container With Most Water (LC 11)
# ══════════════════════════════════════════════════════════════════
def maxArea(height: List[int]) -> int:
    """
    Find two lines that together with the x-axis form a container
    holding the most water.

    Approach: Two pointers. Area = min(height[lo], height[hi]) * (hi - lo).
    Move the pointer pointing to the shorter line inward.

    Example:
      [1,8,6,2,5,4,8,3,7] → 49
      [1,1] → 1
    """
    lo, hi = 0, len(height) - 1
    max_water = 0
    while lo < hi:
        water = min(height[lo], height[hi]) * (hi - lo)
        max_water = max(max_water, water)
        if height[lo] < height[hi]:
            lo += 1
        else:
            hi -= 1
    return max_water

print("\n=== Container With Most Water ===")
print(maxArea([1,8,6,2,5,4,8,3,7]))  # 49
print(maxArea([1,1]))                 # 1
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 4: Trapping Rain Water (LC 42)
# ══════════════════════════════════════════════════════════════════
def trap(height: List[int]) -> int:
    """
    Calculate how much rainwater can be trapped.

    Approach: Two pointers with running max from left and right.
    Water at position i = min(max_left, max_right) - height[i].
    Process from the side with smaller max.

    Example:
      [0,1,0,2,1,0,1,3,2,1,2,1] → 6
      [4,2,0,3,2,5] → 9
    """
    lo, hi = 0, len(height) - 1
    left_max = right_max = 0
    water = 0
    while lo < hi:
        if height[lo] < height[hi]:
            if height[lo] >= left_max:
                left_max = height[lo]
            else:
                water += left_max - height[lo]
            lo += 1
        else:
            if height[hi] >= right_max:
                right_max = height[hi]
            else:
                water += right_max - height[hi]
            hi -= 1
    return water

print("\n=== Trapping Rain Water ===")
print(trap([0,1,0,2,1,0,1,3,2,1,2,1]))  # 6
print(trap([4,2,0,3,2,5]))               # 9
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 5: Move Zeroes (LC 283)
# ══════════════════════════════════════════════════════════════════
def moveZeroes(nums: List[int]) -> None:
    """
    Move all zeros to the end while maintaining the relative order
    of non-zero elements. Modify in-place.

    Approach: Fast/slow two pointers. slow tracks where to place
    the next non-zero. fast scans ahead.

    Example:
      [0,1,0,3,12] → [1,3,12,0,0]
      [0] → [0]
    """
    slow = 0
    for fast in range(len(nums)):
        if nums[fast] != 0:
            nums[slow], nums[fast] = nums[fast], nums[slow]
            slow += 1

print("\n=== Move Zeroes ===")
nums = [0,1,0,3,12]
moveZeroes(nums)
print(nums)  # [1,3,12,0,0]
nums2 = [0]
moveZeroes(nums2)
print(nums2)  # [0]
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 6: Minimum Size Subarray Sum (LC 209)
# ══════════════════════════════════════════════════════════════════
def minSubArrayLen(target: int, nums: List[int]) -> int:
    """
    Find the minimum length subarray with sum >= target.
    Return 0 if no such subarray exists.

    Approach: Variable sliding window. Expand hi, shrink lo while
    current sum >= target (record minimum and keep shrinking).

    Example:
      target=7, nums=[2,3,1,2,4,3] → 2 ([4,3])
      target=4, nums=[1,4,4] → 1
      target=11, nums=[1,1,1,1,1,1,1,1] → 0
    """
    lo = 0
    window_sum = 0
    min_len = float('inf')

    for hi in range(len(nums)):
        window_sum += nums[hi]
        while window_sum >= target:
            min_len = min(min_len, hi - lo + 1)
            window_sum -= nums[lo]
            lo += 1

    return min_len if min_len != float('inf') else 0

print("\n=== Minimum Size Subarray Sum ===")
print(minSubArrayLen(7, [2,3,1,2,4,3]))    # 2
print(minSubArrayLen(4, [1,4,4]))           # 1
print(minSubArrayLen(11, [1,1,1,1,1,1,1,1])) # 0
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 7: Permutation in String (LC 567)
# ══════════════════════════════════════════════════════════════════
def checkInclusion(s1: str, s2: str) -> bool:
    """
    Return True if any permutation of s1 is a substring of s2.

    Approach: Fixed sliding window of size len(s1).
    Track character counts. Window matches when all counts are 0.

    Example:
      s1="ab", s2="eidbaooo" → True (s2 contains "ba")
      s1="ab", s2="eidboaoo" → False
    """
    if len(s1) > len(s2):
        return False
    k = len(s1)
    need = Counter(s1)
    window = Counter(s2[:k])

    if window == need:
        return True

    for i in range(k, len(s2)):
        # Add new character
        window[s2[i]] += 1
        # Remove old character
        old = s2[i - k]
        window[old] -= 1
        if window[old] == 0:
            del window[old]
        if window == need:
            return True

    return False

print("\n=== Permutation in String ===")
print(checkInclusion("ab", "eidbaooo"))  # True
print(checkInclusion("ab", "eidboaoo"))  # False
# Time: O(n) | Space: O(1) — alphabet size is constant

# ══════════════════════════════════════════════════════════════════
# Problem 8: Fruit Into Baskets (LC 904)
# ══════════════════════════════════════════════════════════════════
def totalFruit(fruits: List[int]) -> int:
    """
    You have two baskets; each basket holds one type of fruit.
    Pick fruits starting from any tree, moving right. No skipping.
    Find the maximum number of fruits you can pick.
    = Longest subarray with at most 2 distinct values.

    Approach: Variable sliding window with a frequency map.
    Shrink when more than 2 distinct fruit types in window.

    Example:
      [1,2,1] → 3
      [0,1,2,2] → 3 ([1,2,2])
      [1,2,3,2,2] → 4 ([2,3,2,2])
    """
    basket = defaultdict(int)
    lo = 0
    result = 0

    for hi in range(len(fruits)):
        basket[fruits[hi]] += 1
        while len(basket) > 2:
            basket[fruits[lo]] -= 1
            if basket[fruits[lo]] == 0:
                del basket[fruits[lo]]
            lo += 1
        result = max(result, hi - lo + 1)

    return result

print("\n=== Fruit Into Baskets ===")
print(totalFruit([1,2,1]))       # 3
print(totalFruit([0,1,2,2]))     # 3
print(totalFruit([1,2,3,2,2]))   # 4
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 9: Longest Subarray of 1's After Deleting One Element (LC 1493)
# ══════════════════════════════════════════════════════════════════
def longestSubarray(nums: List[int]) -> int:
    """
    Delete exactly one element. Return the length of the longest subarray
    of 1's after the deletion.

    Approach: Sliding window with at most one 0 allowed.
    When zeros > 1, shrink from left.

    Example:
      [1,1,0,1] → 3
      [0,1,1,1,0,1,1,0,1] → 5
      [1,1,1] → 2 (must delete one)
    """
    lo = 0
    zeros = 0
    result = 0

    for hi in range(len(nums)):
        if nums[hi] == 0:
            zeros += 1
        while zeros > 1:
            if nums[lo] == 0:
                zeros -= 1
            lo += 1
        # Window is hi-lo+1, but we must delete one, so length is hi-lo
        result = max(result, hi - lo)

    return result

print("\n=== Longest Subarray of 1s After Deleting One Element ===")
print(longestSubarray([1,1,0,1]))           # 3
print(longestSubarray([0,1,1,1,0,1,1,0,1])) # 5
print(longestSubarray([1,1,1]))             # 2
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 10: Maximum Points You Can Obtain From Cards (LC 1423)
# ══════════════════════════════════════════════════════════════════
def maxScore(cardPoints: List[int], k: int) -> int:
    """
    Take exactly k cards from either end of the row. Maximize total points.

    Approach: Instead of thinking about taking k from ends,
    think about leaving a window of (n-k) cards in the middle.
    Minimize the sum of the middle window → maximize the endpoints sum.

    Alternative: Sliding window on the k cards selected.

    Example:
      cardPoints=[1,2,3,4,5,6,1], k=3 → 12 (1+6+5)
      cardPoints=[2,2,2], k=2 → 4
    """
    n = len(cardPoints)
    total = sum(cardPoints)
    window_size = n - k  # size of middle window to MINIMIZE

    if window_size == 0:
        return total

    window_sum = sum(cardPoints[:window_size])
    min_window = window_sum

    for i in range(window_size, n):
        window_sum += cardPoints[i] - cardPoints[i - window_size]
        min_window = min(min_window, window_sum)

    return total - min_window

print("\n=== Maximum Points From Cards ===")
print(maxScore([1,2,3,4,5,6,1], 3))  # 12
print(maxScore([2,2,2], 2))           # 4
print(maxScore([9,7,7,9,7,7,9], 7))  # 55
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 11: 4Sum (LC 18)
# ══════════════════════════════════════════════════════════════════
def fourSum(nums: List[int], target: int) -> List[List[int]]:
    """
    Find all unique quadruplets that sum to target.

    Approach: Sort + two outer loops + two pointers inner loop.
    Skip duplicates at all four positions.

    Example:
      nums=[1,0,-1,0,-2,2], target=0 → [[-2,-1,1,2],[-2,0,0,2],[-1,0,0,1]]
      nums=[2,2,2,2,2], target=8 → [[2,2,2,2]]
    """
    nums.sort()
    result = []
    n = len(nums)

    for i in range(n - 3):
        if i > 0 and nums[i] == nums[i-1]:
            continue
        for j in range(i + 1, n - 2):
            if j > i + 1 and nums[j] == nums[j-1]:
                continue
            lo, hi = j + 1, n - 1
            while lo < hi:
                s = nums[i] + nums[j] + nums[lo] + nums[hi]
                if s == target:
                    result.append([nums[i], nums[j], nums[lo], nums[hi]])
                    while lo < hi and nums[lo] == nums[lo+1]: lo += 1
                    while lo < hi and nums[hi] == nums[hi-1]: hi -= 1
                    lo += 1; hi -= 1
                elif s < target:
                    lo += 1
                else:
                    hi -= 1
    return result

print("\n=== 4Sum ===")
print(fourSum([1,0,-1,0,-2,2], 0))  # [[-2,-1,1,2],[-2,0,0,2],[-1,0,0,1]]
print(fourSum([2,2,2,2,2], 8))      # [[2,2,2,2]]
# Time: O(n³) | Space: O(1) excl. output

# ══════════════════════════════════════════════════════════════════
# Problem 12: Sort Array By Parity (LC 905)
# ══════════════════════════════════════════════════════════════════
def sortArrayByParity(nums: List[int]) -> List[int]:
    """
    Move all even integers to the beginning, odd to the end.
    Any valid ordering is acceptable.

    Approach: Two pointers. lo seeks odd (should be right),
    hi seeks even (should be left). Swap when both found.

    Example:
      [3,1,2,4] → [4,2,1,3] (or any valid)
      [0] → [0]
    """
    lo, hi = 0, len(nums) - 1
    while lo < hi:
        if nums[lo] % 2 == 0:
            lo += 1
        elif nums[hi] % 2 == 1:
            hi -= 1
        else:
            nums[lo], nums[hi] = nums[hi], nums[lo]
            lo += 1
            hi -= 1
    return nums

print("\n=== Sort Array By Parity ===")
print(sortArrayByParity([3,1,2,4]))  # [4,2,1,3] or similar
print(sortArrayByParity([0]))         # [0]
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 13: 3Sum Closest (LC 16)
# ══════════════════════════════════════════════════════════════════
def threeSumClosest(nums: List[int], target: int) -> int:
    """
    Given an array of n integers, find three integers whose sum is
    closest to target. Return that sum.

    Approach: Sort. For each element, use two pointers on the rest
    to search for the closest sum, updating the running best.

    Example:
      [-1,2,1,-4], target=1 → 2   (-1+2+1)
      [0,0,0], target=1 → 0
    """
    nums.sort()
    n = len(nums)
    closest = nums[0] + nums[1] + nums[2]

    for i in range(n - 2):
        lo, hi = i + 1, n - 1
        while lo < hi:
            s = nums[i] + nums[lo] + nums[hi]
            if abs(s - target) < abs(closest - target):
                closest = s
            if s == target:
                return s
            elif s < target:
                lo += 1
            else:
                hi -= 1

    return closest

print("\n=== 3Sum Closest ===")
print(threeSumClosest([-1,2,1,-4], 1))  # 2
print(threeSumClosest([0,0,0], 1))       # 0
# Time: O(n²) | Space: O(1) excl. sort

# ══════════════════════════════════════════════════════════════════
# Problem 14: Next Permutation (LC 31)
# ══════════════════════════════════════════════════════════════════
def nextPermutation(nums: List[int]) -> None:
    """
    Rearrange nums into the lexicographically next greater permutation
    in-place. If no such permutation exists (already the largest),
    rearrange to the lowest (sorted ascending).

    Approach: Two pointers.
    1. Scan from the right to find the first index i where
       nums[i] < nums[i+1] (the "pivot").
    2. If found, scan from the right to find the first index j where
       nums[j] > nums[i], and swap them.
    3. Reverse the suffix after i (it was non-increasing, reversing
       makes it the smallest arrangement).

    Example:
      [1,2,3] → [1,3,2]
      [3,2,1] → [1,2,3]
      [1,1,5] → [1,5,1]
    """
    n = len(nums)
    i = n - 2
    while i >= 0 and nums[i] >= nums[i + 1]:
        i -= 1

    if i >= 0:
        j = n - 1
        while nums[j] <= nums[i]:
            j -= 1
        nums[i], nums[j] = nums[j], nums[i]

    lo, hi = i + 1, n - 1
    while lo < hi:
        nums[lo], nums[hi] = nums[hi], nums[lo]
        lo += 1
        hi -= 1

print("\n=== Next Permutation ===")
nums = [1,2,3]
nextPermutation(nums)
print(nums)  # [1,3,2]
nums2 = [3,2,1]
nextPermutation(nums2)
print(nums2)  # [1,2,3]
nums3 = [1,1,5]
nextPermutation(nums3)
print(nums3)  # [1,5,1]
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 15: Rotate Array (LC 189)
# ══════════════════════════════════════════════════════════════════
def rotate(nums: List[int], k: int) -> None:
    """
    Rotate the array to the right by k steps, in-place.

    Approach: Three reversals.
    1. Reverse the whole array.
    2. Reverse the first k elements.
    3. Reverse the remaining n-k elements.
    This effectively rotates the array right by k.

    Example:
      [1,2,3,4,5,6,7], k=3 → [5,6,7,1,2,3,4]
      [-1,-100,3,99], k=2 → [3,99,-1,-100]
    """
    n = len(nums)
    k %= n

    def reverse(lo, hi):
        while lo < hi:
            nums[lo], nums[hi] = nums[hi], nums[lo]
            lo += 1
            hi -= 1

    reverse(0, n - 1)
    reverse(0, k - 1)
    reverse(k, n - 1)

print("\n=== Rotate Array ===")
nums4 = [1,2,3,4,5,6,7]
rotate(nums4, 3)
print(nums4)  # [5,6,7,1,2,3,4]
nums5 = [-1,-100,3,99]
rotate(nums5, 2)
print(nums5)  # [3,99,-1,-100]
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 16: Squares of a Sorted Array (LC 977)
# ══════════════════════════════════════════════════════════════════
def sortedSquares(nums: List[int]) -> List[int]:
    """
    Given an array sorted in non-decreasing order, return an array
    of the squares of each number, also sorted in non-decreasing order.

    Approach: Two pointers from both ends (largest absolute values
    are at the ends since the array can contain negatives). Fill
    the result array from the back with the larger square each step.

    Example:
      [-4,-1,0,3,10] → [0,1,9,16,100]
      [-7,-3,2,3,11] → [4,9,9,49,121]
    """
    n = len(nums)
    result = [0] * n
    lo, hi = 0, n - 1

    for pos in range(n - 1, -1, -1):
        if abs(nums[lo]) > abs(nums[hi]):
            result[pos] = nums[lo] ** 2
            lo += 1
        else:
            result[pos] = nums[hi] ** 2
            hi -= 1

    return result

print("\n=== Squares of a Sorted Array ===")
print(sortedSquares([-4,-1,0,3,10]))  # [0, 1, 9, 16, 100]
print(sortedSquares([-7,-3,2,3,11]))  # [4, 9, 9, 49, 121]
# Time: O(n) | Space: O(n)

print("\n✓ All 16 Two Pointers & Sliding Window problems solved!")
