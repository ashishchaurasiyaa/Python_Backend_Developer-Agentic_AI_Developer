"""19 — Math & Number Theory — Problems | 12 problems | Easy→Hard"""
from typing import List
import math

# ─────────────────────────────────────────────
# P01. Count Primes  [Medium][LC 204]
# ─────────────────────────────────────────────
"""Count primes strictly less than n. Input: 10 → Output: 4 (2,3,5,7)"""
def countPrimes(n: int) -> int:
    if n < 2: return 0
    is_prime = [True] * n
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(n**0.5) + 1):
        if is_prime[i]:
            for j in range(i*i, n, i):
                is_prime[j] = False
    return sum(is_prime)

print("P01:", countPrimes(10))   # 4
print("P01:", countPrimes(100))  # 25


# ─────────────────────────────────────────────
# P02. Power of Two  [Easy][LC 231]
# ─────────────────────────────────────────────
"""Return true if n is a power of two."""
def isPowerOfTwo(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0

print("P02:", isPowerOfTwo(16))  # True
print("P02:", isPowerOfTwo(18))  # False


# ─────────────────────────────────────────────
# P03. Factorial Trailing Zeroes  [Medium][LC 172]
# ─────────────────────────────────────────────
"""Count trailing zeros in n! in O(log n)."""
def trailingZeroes(n: int) -> int:
    count = 0
    while n >= 5:
        n //= 5
        count += n
    return count

print("P03:", trailingZeroes(5))    # 1
print("P03:", trailingZeroes(100))  # 24


# ─────────────────────────────────────────────
# P04. Happy Number  [Easy][LC 202]
# ─────────────────────────────────────────────
"""
Repeatedly replace n with sum of squares of its digits.
Return True if it reaches 1. Use Floyd's cycle detection.
"""
def isHappy(n: int) -> bool:
    def sq_sum(x): return sum(int(d)**2 for d in str(x))
    slow, fast = n, sq_sum(n)
    while fast != 1 and slow != fast:
        slow = sq_sum(slow)
        fast = sq_sum(sq_sum(fast))
    return fast == 1

print("P04:", isHappy(19))  # True
print("P04:", isHappy(2))   # False


# ─────────────────────────────────────────────
# P05. Excel Sheet Column Number  [Easy][LC 171]
# ─────────────────────────────────────────────
"""A→1, B→2, ..., Z→26, AA→27, AB→28"""
def titleToNumber(columnTitle: str) -> int:
    result = 0
    for c in columnTitle:
        result = result * 26 + (ord(c) - ord('A') + 1)
    return result

print("P05:", titleToNumber("A"))    # 1
print("P05:", titleToNumber("Z"))    # 26
print("P05:", titleToNumber("AA"))   # 27
print("P05:", titleToNumber("ZY"))   # 701


# ─────────────────────────────────────────────
# P06. Pow(x, n)  [Medium][LC 50]
# ─────────────────────────────────────────────
"""Implement x^n. Handle negative n and n=0."""
def myPow(x: float, n: int) -> float:
    if n < 0:
        x, n = 1 / x, -n
    result = 1.0
    while n:
        if n & 1:
            result *= x
        x *= x
        n >>= 1
    return result

print("P06:", myPow(2.0, 10))    # 1024.0
print("P06:", myPow(2.0, -2))    # 0.25
print("P06:", myPow(2.10, 3))    # 9.261...


# ─────────────────────────────────────────────
# P07. Sqrt(x)  [Easy][LC 69]
# ─────────────────────────────────────────────
"""Return floor(sqrt(x)) without using sqrt. Binary search."""
def mySqrt(x: int) -> int:
    if x < 2: return x
    lo, hi = 1, x // 2
    while lo <= hi:
        mid = (lo + hi) // 2
        if mid * mid == x:   return mid
        elif mid * mid < x:  lo = mid + 1
        else:                hi = mid - 1
    return hi  # hi = floor(sqrt(x))

print("P07:", mySqrt(4))   # 2
print("P07:", mySqrt(8))   # 2
print("P07:", mySqrt(25))  # 5


# ─────────────────────────────────────────────
# P08. Integer to Roman  [Medium][LC 12]
# ─────────────────────────────────────────────
"""Greedy: subtract largest possible Roman numeral value at each step."""
def intToRoman(num: int) -> str:
    val_sym = [
        (1000,"M"),(900,"CM"),(500,"D"),(400,"CD"),
        (100,"C"),(90,"XC"),(50,"L"),(40,"XL"),
        (10,"X"),(9,"IX"),(5,"V"),(4,"IV"),(1,"I")
    ]
    result = ""
    for val, sym in val_sym:
        while num >= val:
            result += sym
            num -= val
    return result

print("P08:", intToRoman(3749))   # "MMMDCCXLIX"
print("P08:", intToRoman(1994))   # "MCMXCIV"


# ─────────────────────────────────────────────
# P09. Ugly Number II  [Medium][LC 264]
# ─────────────────────────────────────────────
"""
Ugly numbers: only prime factors 2, 3, 5.
Find nth ugly number. Three-pointer DP.
Input: 10 → Output: 12 (1,2,3,4,5,6,8,9,10,12)
"""
def nthUglyNumber(n: int) -> int:
    ugly = [1] * n
    i2 = i3 = i5 = 0
    for i in range(1, n):
        next2, next3, next5 = ugly[i2]*2, ugly[i3]*3, ugly[i5]*5
        ugly[i] = min(next2, next3, next5)
        if ugly[i] == next2: i2 += 1
        if ugly[i] == next3: i3 += 1
        if ugly[i] == next5: i5 += 1
    return ugly[n-1]

print("P09:", nthUglyNumber(10))  # 12
print("P09:", nthUglyNumber(1))   # 1


# ─────────────────────────────────────────────
# P10. Perfect Squares  [Medium][LC 279]
# ─────────────────────────────────────────────
"""
Min number of perfect squares that sum to n.
BFS approach: levels = min count. DP also works.
Lagrange's theorem: answer is always 1, 2, 3, or 4.
"""
def numSquares(n: int) -> int:
    # DP: dp[i] = min squares summing to i
    dp = [float('inf')] * (n + 1)
    dp[0] = 0
    squares = []
    i = 1
    while i * i <= n:
        squares.append(i * i)
        i += 1
    for i in range(1, n + 1):
        for sq in squares:
            if sq > i: break
            dp[i] = min(dp[i], dp[i - sq] + 1)
    return dp[n]

print("P10:", numSquares(12))  # 3 (4+4+4)
print("P10:", numSquares(13))  # 2 (4+9)


# ─────────────────────────────────────────────
# P11. Nth Digit  [Medium][LC 400]
# ─────────────────────────────────────────────
"""
Infinite sequence: 1 2 3 4 5 6 7 8 9 10 11 12 ...
Find nth digit. n=11 → '0' (from 10).
Math: find which "digit-length group" n falls in.
"""
def findNthDigit(n: int) -> int:
    digits = 1
    count = 9
    start = 1
    # Find the digit-length group
    while n > digits * count:
        n -= digits * count
        digits += 1
        count *= 10
        start *= 10
    # Find the actual number
    num = start + (n - 1) // digits
    # Find the digit within that number
    digit_index = (n - 1) % digits
    return int(str(num)[digit_index])

print("P11:", findNthDigit(3))    # 3
print("P11:", findNthDigit(11))   # 0  (from "10")
print("P11:", findNthDigit(15))   # 2  (from "12")


# ─────────────────────────────────────────────
# P12. Super Pow  [Medium][LC 372]
# ─────────────────────────────────────────────
"""
Compute a^b mod 1337, where b is given as an array of digits.
Key insight: a^(bc) = (a^b)^c → process digits from right to left.
a^[1,2,3] = a^3 * (a^[1,2])^10
"""
def superPow(a: int, b: List[int]) -> int:
    MOD = 1337

    def pow_mod(base, exp, mod):
        result = 1
        base %= mod
        while exp:
            if exp & 1: result = result * base % mod
            base = base * base % mod
            exp >>= 1
        return result

    result = 1
    for digit in b:
        result = pow_mod(result, 10, MOD) * pow_mod(a, digit, MOD) % MOD
    return result

print("P12:", superPow(2, [1,0]))         # 1024 % 1337 = 1024
print("P12:", superPow(2, [3]))           # 8
print("P12:", superPow(1, [4,3,3,8,5,2])) # 1


"""
COMPLEXITY SUMMARY:
─────────────────────────────────────────────
Count Primes          O(n log log n) O(n)  Sieve
Power of Two          O(1)           O(1)  Bit trick n&(n-1)
Trailing Zeroes       O(log n)       O(1)  Count 5-factors
Happy Number          O(log n)       O(1)  Floyd's cycle
Excel Column Number   O(k)           O(1)  Base-26 decode
Pow(x,n)              O(log n)       O(1)  Binary exponentiation
Sqrt(x)               O(log n)       O(1)  Binary search
Integer to Roman      O(1)           O(1)  Greedy (13 values)
Ugly Number II        O(n)           O(n)  3-pointer DP
Perfect Squares       O(n√n)         O(n)  DP
Nth Digit             O(log n)       O(1)  Math digit groups
Super Pow             O(len(b))      O(1)  Modular exponentiation
"""
