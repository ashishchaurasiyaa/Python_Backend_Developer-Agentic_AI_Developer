"""
╔══════════════════════════════════════════════════════════════════╗
║             BIT MANIPULATION — 10 LeetCode-Style Problems        ║
╚══════════════════════════════════════════════════════════════════╝
"""

from typing import List

# ══════════════════════════════════════════════════════════════════
# Problem 1: Single Number (LC 136) — XOR
# ══════════════════════════════════════════════════════════════════
def singleNumber(nums: List[int]) -> int:
    """
    Every element appears twice except one. Find that single number.

    XOR approach: a ^ a = 0, a ^ 0 = a. XOR all numbers.
    Pairs cancel out, leaving the single number.

    Example:
      [2,2,1] → 1
      [4,1,2,1,2] → 4
    """
    result = 0
    for n in nums:
        result ^= n
    return result

print("=== Single Number ===")
print(singleNumber([2,2,1]))       # 1
print(singleNumber([4,1,2,1,2]))   # 4
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 2: Number of 1 Bits (LC 191) — Hamming Weight
# ══════════════════════════════════════════════════════════════════
def hammingWeight(n: int) -> int:
    """
    Return the number of '1' bits (Hamming weight) of a 32-bit integer.

    Approach: Brian Kernighan's — n & (n-1) removes lowest set bit.
    Count until n becomes 0.

    Example:
      00000000000000000000000000001011 → 3
      11111111111111111111111111111101 → 31
    """
    count = 0
    while n:
        n &= (n - 1)  # remove lowest set bit
        count += 1
    return count

print("\n=== Number of 1 Bits (Hamming Weight) ===")
print(hammingWeight(0b00000000000000000000000000001011))  # 3
print(hammingWeight(0b11111111111111111111111111111101))  # 31
# Time: O(k) where k = number of 1s | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 3: Counting Bits (LC 338)
# ══════════════════════════════════════════════════════════════════
def countBits(n: int) -> List[int]:
    """
    For each i from 0 to n, count the number of 1 bits.

    DP: dp[i] = dp[i >> 1] + (i & 1)
    i >> 1 removes the last bit (halving i).
    i & 1 adds 1 if i is odd (last bit is 1).

    Example:
      n=2 → [0,1,1]
      n=5 → [0,1,1,2,1,2]
    """
    dp = [0] * (n + 1)
    for i in range(1, n + 1):
        dp[i] = dp[i >> 1] + (i & 1)
    return dp

print("\n=== Counting Bits ===")
print(countBits(2))  # [0,1,1]
print(countBits(5))  # [0,1,1,2,1,2]
# Time: O(n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 4: Reverse Bits (LC 190)
# ══════════════════════════════════════════════════════════════════
def reverseBits(n: int) -> int:
    """
    Reverse the bits of a 32-bit unsigned integer.

    Approach: Extract last bit of n, shift it into result from the right.
    Repeat 32 times.

    Example:
      00000010100101000001111010011100 → 964176192 (reversed)
    """
    result = 0
    for _ in range(32):
        result = (result << 1) | (n & 1)
        n >>= 1
    return result

print("\n=== Reverse Bits ===")
n = 0b00000010100101000001111010011100
print(reverseBits(n))   # 964176192
print(bin(reverseBits(n)))
# Time: O(32) = O(1) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 5: Missing Number (LC 268) — XOR
# ══════════════════════════════════════════════════════════════════
def missingNumber(nums: List[int]) -> int:
    """
    nums contains n distinct numbers in range [0,n]. Find the missing number.

    XOR approach: XOR all indices 0..n and all values.
    Pairs cancel. Missing index/value remains.

    Alternative: Sum formula n*(n+1)//2 - sum(nums).

    Example:
      [3,0,1] → 2
      [0,1] → 2
      [9,6,4,2,3,5,7,0,1] → 8
    """
    result = len(nums)  # XOR with n (the missing candidate)
    for i, num in enumerate(nums):
        result ^= i ^ num
    return result

print("\n=== Missing Number ===")
print(missingNumber([3,0,1]))               # 2
print(missingNumber([0,1]))                 # 2
print(missingNumber([9,6,4,2,3,5,7,0,1]))  # 8
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 6: Sum of Two Integers Without + (LC 371)
# ══════════════════════════════════════════════════════════════════
def getSum(a: int, b: int) -> int:
    """
    Calculate sum of two integers without using + or -.

    Approach:
      - XOR gives sum without carry: a ^ b
      - AND gives carry bits: (a & b) << 1
      - Repeat until no carry.

    Python uses arbitrary precision ints, so need 32-bit mask.

    Example:
      1 + 2 → 3
      -2 + 3 → 1
    """
    MASK = 0xFFFFFFFF
    MAX = 0x7FFFFFFF

    while b:
        carry = ((a & b) << 1) & MASK
        a = (a ^ b) & MASK
        b = carry

    return a if a <= MAX else ~(a ^ MASK)

print("\n=== Sum of Two Integers Without + ===")
print(getSum(1, 2))   # 3
print(getSum(-2, 3))  # 1
print(getSum(0, 0))   # 0
# Time: O(1) for 32-bit ints | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 7: Power of Two (LC 231)
# ══════════════════════════════════════════════════════════════════
def isPowerOfTwo(n: int) -> bool:
    """
    Determine if n is a power of 2.

    Bit trick: Powers of 2 have exactly one '1' bit.
    n & (n-1) clears the lowest set bit.
    If n > 0 and n & (n-1) == 0 → exactly one '1' bit → power of 2.

    Example:
      1 → True (2^0)
      16 → True (2^4)
      3 → False
      -16 → False
    """
    return n > 0 and (n & (n - 1)) == 0

print("\n=== Power of Two ===")
print(isPowerOfTwo(1))   # True
print(isPowerOfTwo(16))  # True
print(isPowerOfTwo(3))   # False
print(isPowerOfTwo(-16)) # False
# Time: O(1) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 8: Maximum XOR of Two Numbers in an Array (LC 421)
# ══════════════════════════════════════════════════════════════════
def findMaximumXOR(nums: List[int]) -> int:
    """
    Find maximum XOR of any two numbers in the array.

    Greedy Bit-by-Bit approach:
    From MSB to LSB, try to set each bit to 1.
    Use a prefix set to check if XOR with desired bit is achievable.

    Key: If a ^ b == prefix → b = a ^ prefix.
    Check if any b in prefix_set satisfies this.

    Example:
      [3,10,5,25,2,8] → 28 (5^25)
    """
    max_xor = 0
    mask = 0

    for i in range(31, -1, -1):
        mask |= (1 << i)
        prefix_set = {num & mask for num in nums}  # set of prefixes up to bit i

        # Try to set bit i in max_xor
        target = max_xor | (1 << i)

        for prefix in prefix_set:
            if prefix ^ target in prefix_set:
                max_xor = target
                break

    return max_xor

print("\n=== Maximum XOR of Two Numbers ===")
print(findMaximumXOR([3,10,5,25,2,8]))   # 28
print(findMaximumXOR([14,70,53,83,49,91,36,80,92,51,66,70]))  # 127
# Time: O(32 * n) = O(n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 9: Subsets via Bitmask (LC 78)
# ══════════════════════════════════════════════════════════════════
def subsets(nums: List[int]) -> List[List[int]]:
    """
    Generate all subsets using bitmask enumeration.
    For n elements, there are 2^n subsets (masks from 0 to 2^n - 1).
    Bit i of mask = include/exclude nums[i].

    Example:
      [1,2,3] → [[],[1],[2],[1,2],[3],[1,3],[2,3],[1,2,3]]
    """
    n = len(nums)
    result = []
    for mask in range(1 << n):  # 0 to 2^n - 1
        subset = []
        for i in range(n):
            if mask & (1 << i):
                subset.append(nums[i])
        result.append(subset)
    return result

print("\n=== Subsets via Bitmask ===")
print(subsets([1,2,3]))
# All 8 subsets: [[],[1],[2],[1,2],[3],[1,3],[2,3],[1,2,3]]
# Time: O(n * 2^n) | Space: O(n * 2^n)

# ══════════════════════════════════════════════════════════════════
# Problem 10: Bonus — Single Number III (LC 260) — Two unique numbers
# ══════════════════════════════════════════════════════════════════
def singleNumberIII(nums: List[int]) -> List[int]:
    """
    Every element appears twice EXCEPT two numbers. Find those two.

    Approach:
    1. XOR all numbers → result = a ^ b (the two unique numbers).
    2. Find any set bit in result (a and b differ in this bit).
    3. Partition nums into two groups based on this bit.
    4. XOR each group → find a and b separately.

    Example:
      [1,2,1,3,2,5] → [3,5]
    """
    xor = 0
    for n in nums:
        xor ^= n
    # Find rightmost set bit (a and b differ here)
    diff_bit = xor & (-xor)

    a = b = 0
    for n in nums:
        if n & diff_bit:
            a ^= n
        else:
            b ^= n
    return sorted([a, b])

print("\n=== Single Number III (Two Unique Numbers) ===")
print(singleNumberIII([1,2,1,3,2,5]))  # [3,5]
print(singleNumberIII([1,2]))          # [1,2]
# Time: O(n) | Space: O(1)

print("\n" + "=" * 60)
print("BIT MANIPULATION QUICK REFERENCE")
print("=" * 60)
cheat = """
n & (1 << i)       → check if bit i is set
n | (1 << i)       → set bit i
n & ~(1 << i)      → clear bit i
n ^ (1 << i)       → toggle bit i
n & (n-1)          → clear lowest set bit / check power of 2
n & (-n)           → isolate lowest set bit
n >> k             → divide by 2^k (floor)
n << k             → multiply by 2^k
a ^ a = 0          → cancel pairs with XOR
a ^ 0 = a          → XOR identity
bin(n).count('1')  → count set bits (Python)
n.bit_count()      → count set bits (Python 3.10+)
n.bit_length()     → number of bits needed
range(1 << n)      → iterate all subsets of n elements
"""
print(cheat)

print("\n✓ All 10 Bit Manipulation problems solved!")
