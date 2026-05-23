"""
╔══════════════════════════════════════════════════════════════════╗
║             BIT MANIPULATION — Complete Theory Guide             ║
╚══════════════════════════════════════════════════════════════════╝

WHAT IS BIT MANIPULATION?
──────────────────────────
Operating directly on the binary representation of numbers using
bitwise operators. Extremely fast (single CPU instruction) and
space-efficient. Common in competitive programming and systems code.

BINARY REPRESENTATION
──────────────────────
  Integer 13 = 1101₂
  Position:    3 2 1 0  (bit positions, right to left)
  Value:       8 4 2 1
  13 = 8 + 4 + 0 + 1

BITWISE OPERATORS IN PYTHON
─────────────────────────────
  a & b   AND:   1 if both 1
  a | b   OR:    1 if either 1
  a ^ b   XOR:   1 if exactly one is 1
  ~a      NOT:   flip all bits (= -(a+1) in Python)
  a << k  Left shift by k: multiply by 2^k
  a >> k  Right shift by k: divide by 2^k (floor)
"""

print("=" * 60)
print("1. BITWISE OPERATORS")
print("=" * 60)

a, b = 12, 10   # 1100, 1010
print(f"a={a} ({bin(a)}), b={b} ({bin(b)})")
print(f"a & b  = {a & b}  ({bin(a & b)})")   # 8 = 1000
print(f"a | b  = {a | b}  ({bin(a | b)})")   # 14 = 1110
print(f"a ^ b  = {a ^ b}  ({bin(a ^ b)})")   # 6 = 0110
print(f"~a     = {~a}     (bitwise NOT)")     # -13
print(f"a << 2 = {a << 2} ({bin(a << 2)})")  # 48 = 110000
print(f"a >> 2 = {a >> 2} ({bin(a >> 2)})")  # 3 = 11

# ─────────────────────────────────────────────
# 2. COMMON BIT TRICKS
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("2. COMMON BIT TRICKS")
print("=" * 60)

# Check if bit i is set
def is_bit_set(n: int, i: int) -> bool:
    return bool(n & (1 << i))

# Set bit i
def set_bit(n: int, i: int) -> int:
    return n | (1 << i)

# Clear bit i
def clear_bit(n: int, i: int) -> int:
    return n & ~(1 << i)

# Toggle bit i
def toggle_bit(n: int, i: int) -> int:
    return n ^ (1 << i)

n = 13  # 1101
print(f"n={n} ({bin(n)})")
print(f"Bit 2 set? {is_bit_set(n, 2)}")      # True (1101, bit 2 = 1)
print(f"Set bit 1: {set_bit(n, 1)} ({bin(set_bit(n,1))})")    # 15 = 1111
print(f"Clear bit 3: {clear_bit(n, 3)} ({bin(clear_bit(n,3))})")  # 5 = 0101
print(f"Toggle bit 0: {toggle_bit(n, 0)} ({bin(toggle_bit(n,0))})")  # 12 = 1100

# ─────────────────────────────────────────────
# 3. POWER OF 2 CHECK
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("3. POWER OF 2 CHECK")
print("=" * 60)

"""
A power of 2 has exactly ONE bit set.
n = 1000...0 in binary.
n - 1 = 0111...1

n & (n-1) removes the LOWEST SET BIT.
If n is a power of 2, n & (n-1) == 0 (all bits cleared).
"""

def is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0

print(f"isPow2(8)={is_power_of_two(8)}  16={is_power_of_two(16)}  6={is_power_of_two(6)}")

# ─────────────────────────────────────────────
# 4. COUNT SET BITS — Brian Kernighan's Algorithm
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("4. COUNT SET BITS — Brian Kernighan's Algorithm")
print("=" * 60)

"""
n & (n-1) removes the lowest set bit.
Repeat until n becomes 0. Count iterations.
Time: O(number of set bits)

Python has bin(n).count('1') and int.bit_count() in 3.10+.
"""

def count_set_bits(n: int) -> int:
    count = 0
    while n:
        n &= (n - 1)  # remove lowest set bit
        count += 1
    return count

print(f"set bits in 13 (1101): {count_set_bits(13)}")  # 3
print(f"set bits in 255: {count_set_bits(255)}")        # 8
print(f"Python builtin: {(13).bit_count()}")            # 3 (Python 3.10+)

# ─────────────────────────────────────────────
# 5. XOR PROPERTIES — The Magic Trick
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("5. XOR PROPERTIES")
print("=" * 60)

"""
KEY XOR PROPERTIES:
  a ^ 0 = a         (XOR with 0 = identity)
  a ^ a = 0         (XOR with itself = 0)
  a ^ b ^ a = b     (cancellation)
  XOR is commutative and associative

APPLICATIONS:
  - Find the single number in array where all others appear twice
  - Swap two numbers without temp: a^=b; b^=a; a^=b
  - Find missing number: XOR all indices and values
"""

# XOR swap (classic interview trick)
a, b = 5, 3
print(f"Before: a={a}, b={b}")
a ^= b; b ^= a; a ^= b
print(f"After XOR swap: a={a}, b={b}")

# Find single number (all others appear twice)
nums = [4, 1, 2, 1, 2]
result = 0
for n in nums:
    result ^= n
print(f"Single number in {nums}: {result}")  # 4

# ─────────────────────────────────────────────
# 6. COUNTING BITS (DP + Bit Trick)
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("6. COUNTING BITS — DP Approach")
print("=" * 60)

"""
Count set bits for 0..n.

DP formula: dp[i] = dp[i >> 1] + (i & 1)
  i >> 1 = i // 2 (right shift = remove last bit)
  i & 1 = last bit (0 or 1)
  "The count of i equals count of i//2 plus the last bit."
"""

def count_bits_dp(n: int) -> list:
    dp = [0] * (n + 1)
    for i in range(1, n + 1):
        dp[i] = dp[i >> 1] + (i & 1)
    return dp

print(f"Counting bits 0..7: {count_bits_dp(7)}")  # [0,1,1,2,1,2,2,3]

# ─────────────────────────────────────────────
# 7. REVERSE BITS
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("7. REVERSE BITS (32-bit integer)")
print("=" * 60)

def reverse_bits(n: int) -> int:
    """Reverse the 32 bits of a 32-bit unsigned integer."""
    result = 0
    for _ in range(32):
        result = (result << 1) | (n & 1)  # append last bit of n to result
        n >>= 1
    return result

n = 0b00000010100101000001111010011100
print(f"Reversed: {reverse_bits(n)}")  # 964176192

# ─────────────────────────────────────────────
# 8. BITMASK DP — Intro
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("8. BITMASK DP — Introduction")
print("=" * 60)

"""
Bitmask DP uses binary numbers to represent subsets.
For n items: 2^n possible subsets, each represented as an integer mask.

COMMON OPERATIONS:
  Check if item i is in subset s:     s & (1 << i)
  Add item i to subset s:             s | (1 << i)
  Remove item i from subset s:        s & ~(1 << i)
  Iterate all subsets of s:           sub = s; while sub: ...; sub = (sub-1) & s

EXAMPLE: All subsets of {0,1,2} using bitmask:
  000 = {} (empty set)
  001 = {0}
  010 = {1}
  011 = {0,1}
  100 = {2}
  101 = {0,2}
  110 = {1,2}
  111 = {0,1,2}

USE CASE: When n <= 20 and you need to try all subsets.
"""

n_items = 3
print(f"All subsets of {n_items} items using bitmask:")
for mask in range(1 << n_items):
    items = [i for i in range(n_items) if mask & (1 << i)]
    print(f"  mask={bin(mask)[2:].zfill(n_items)} → {items}")

# Bitmask subsets — generating all subsets using bitmask
def subsets_bitmask(nums: list) -> list:
    n = len(nums)
    result = []
    for mask in range(1 << n):
        subset = [nums[i] for i in range(n) if mask & (1 << i)]
        result.append(subset)
    return result

print(f"\nSubsets of [1,2,3]: {subsets_bitmask([1,2,3])}")

# ─────────────────────────────────────────────
# 9. SUM WITHOUT ADDITION (Bit Tricks)
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("9. SUM WITHOUT + OPERATOR")
print("=" * 60)

"""
a + b = (a ^ b) + carry, where carry = (a & b) << 1
Repeat until no carry remains.
"""

def add_without_plus(a: int, b: int) -> int:
    """Works for non-negative integers. For Python, handle negatives via masking."""
    MASK = 0xFFFFFFFF  # 32-bit mask
    MAX = 0x7FFFFFFF   # max positive 32-bit

    while b:
        carry = (a & b) << 1
        a = (a ^ b) & MASK
        b = carry & MASK

    # Handle negative result (if sign bit is set)
    return a if a <= MAX else ~(a ^ MASK)

print(f"1 + 2 = {add_without_plus(1, 2)}")     # 3
print(f"5 + -3 = {add_without_plus(5, -3)}")   # 2 (approximately, 32-bit)

# ─────────────────────────────────────────────
# 10. INTERVIEW Q&A
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("INTERVIEW Q&A")
print("=" * 60)

qa = """
Q1: What is the difference between & and &&?
A1: In Python, there's no &&. & is bitwise AND (works on integers).
    'and' is logical AND (works on booleans, short-circuits).
    Similar for | vs 'or'.

Q2: How do you check if the i-th bit is set?
A2: n & (1 << i). If result is non-zero, bit i is set.

Q3: What does n & (n-1) do?
A3: Clears the lowest set bit of n.
    n=12 (1100), n-1=11 (1011), n&(n-1)=8 (1000).
    Use: count set bits, check power of 2.

Q4: What does n & (-n) do?
A4: Isolates the lowest set bit (returns a power of 2).
    n=12 (1100), -n in two's complement = ...10100 → n&(-n) = 4 (100).

Q5: How do you swap two variables without a temp using XOR?
A5: a ^= b; b ^= a; a ^= b.
    Works because: a^b^a = b and a^b^b = a.
    WARNING: Fails if a and b are the same variable (x^x=0).

Q6: What are XOR's key properties?
A6: a^0 = a, a^a = 0, commutative, associative.
    These enable: finding single number, finding missing number,
    finding two different numbers in an array.

Q7: What is the time complexity of bit manipulation operations?
A7: All bitwise ops (AND, OR, XOR, shift) are O(1) for fixed-size integers.
    For Python's arbitrary-precision integers: O(n) where n = number of bits.

Q8: When would you use bitmask DP?
A8: Problems with small n (≤ 20) where you need to track which items
    have been "used". State space = 2^n. Examples: TSP, assignment problem,
    shortest path visiting all nodes, covering all tasks.
"""
print(qa)
