"""
19 — Math & Number Theory — Theory
====================================
Level: Intermediate → Advanced
"""
import math
from typing import List

# ════════════════════════════════════════════════════════════
# WHAT & WHY
# ════════════════════════════════════════════════════════════
"""
Math shortcuts often turn O(n) or O(n²) brute-force into O(log n) or O(√n).
Key areas in coding interviews:
  - Primes & factorization (LC 204, 264, 279)
  - GCD/LCM (LC 1071, 914)
  - Modular arithmetic (LC 50, 372)
  - Combinatorics (nCr, Pascal's triangle)
  - Number properties (power of 2/3, trailing zeros, digit sum)
  - Fibonacci / matrix exponentiation
"""

# ════════════════════════════════════════════════════════════
# GCD & LCM
# ════════════════════════════════════════════════════════════

def gcd(a: int, b: int) -> int:
    """Euclidean algorithm. O(log min(a,b))."""
    return a if b == 0 else gcd(b, a % b)

def lcm(a: int, b: int) -> int:
    """LCM = a * b / gcd(a, b). Avoid overflow with //."""
    return a * b // math.gcd(a, b)

print("GCD(48,18):", math.gcd(48, 18))   # 6
print("LCM(4,6):", lcm(4, 6))             # 12
# Python 3.9+: math.lcm(a, b)
# Python 3.9+: math.gcd works with multiple args: math.gcd(a, b, c)


# ════════════════════════════════════════════════════════════
# SIEVE OF ERATOSTHENES
# ════════════════════════════════════════════════════════════

def sieve(n: int) -> List[int]:
    """
    Find all primes up to n. O(n log log n) time, O(n) space.
    Key: start from i² (smaller multiples already marked).
    """
    is_prime = [True] * (n + 1)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(n**0.5) + 1):
        if is_prime[i]:
            for j in range(i * i, n + 1, i):
                is_prime[j] = False
    return [i for i in range(2, n + 1) if is_prime[i]]

print("Primes ≤ 30:", sieve(30))  # [2,3,5,7,11,13,17,19,23,29]

def sieve_prefix_count(n: int) -> List[int]:
    """prime_count[i] = number of primes ≤ i. O(n log log n)."""
    is_prime = [True] * (n + 1)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(n**0.5) + 1):
        if is_prime[i]:
            for j in range(i*i, n+1, i):
                is_prime[j] = False
    prime_count = [0] * (n + 1)
    for i in range(1, n + 1):
        prime_count[i] = prime_count[i-1] + (1 if is_prime[i] else 0)
    return prime_count


# ════════════════════════════════════════════════════════════
# PRIME FACTORIZATION
# ════════════════════════════════════════════════════════════

def prime_factors(n: int) -> dict:
    """
    Return dict of {prime: exponent}. Trial division O(√n).
    Example: 12 → {2: 2, 3: 1}
    """
    factors = {}
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors[d] = factors.get(d, 0) + 1
            n //= d
        d += 1
    if n > 1:
        factors[n] = factors.get(n, 0) + 1
    return factors

print("Factors of 360:", prime_factors(360))  # {2:3, 3:2, 5:1}

def is_prime(n: int) -> bool:
    """O(√n) primality check."""
    if n < 2: return False
    if n < 4: return True
    if n % 2 == 0 or n % 3 == 0: return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0: return False
        i += 6
    return True


# ════════════════════════════════════════════════════════════
# FAST EXPONENTIATION (Binary Exponentiation)
# ════════════════════════════════════════════════════════════

def fast_pow(base: int, exp: int, mod: int) -> int:
    """
    Compute base^exp % mod in O(log exp).
    Python's built-in pow(base, exp, mod) does the same thing (C-level, fastest).
    """
    result = 1
    base %= mod
    while exp > 0:
        if exp & 1:                    # if odd exponent, multiply result
            result = result * base % mod
        base = base * base % mod       # square the base
        exp >>= 1                      # halve the exponent
    return result

print("2^10 % 1000:", fast_pow(2, 10, 1000))  # 24
print("Same with pow:", pow(2, 10, 1000))      # 24 (use this in interviews)


# ════════════════════════════════════════════════════════════
# MODULAR ARITHMETIC
# ════════════════════════════════════════════════════════════
"""
(a + b) % m = ((a % m) + (b % m)) % m
(a * b) % m = ((a % m) * (b % m)) % m
(a - b) % m = ((a % m) - (b % m) + m) % m   ← +m to handle negative

MODULAR INVERSE (when mod is prime):
  a^(-1) mod p = a^(p-2) mod p   [Fermat's little theorem]
  Requires: p is prime and gcd(a,p) = 1.
"""

def mod_inverse(a: int, mod: int) -> int:
    """Modular inverse using Fermat's theorem. mod must be prime."""
    return pow(a, mod - 2, mod)

MOD = 10**9 + 7
print("Inverse of 3 mod 1e9+7:", mod_inverse(3, MOD))  # 333333336
# Verify: 3 * 333333336 % (10**9+7) == 1


# ════════════════════════════════════════════════════════════
# COMBINATORICS — nCr mod p
# ════════════════════════════════════════════════════════════

def precompute_factorials(max_n: int, mod: int):
    """Precompute factorials and inverse factorials for O(1) nCr."""
    fact = [1] * (max_n + 1)
    for i in range(1, max_n + 1):
        fact[i] = fact[i-1] * i % mod
    inv_fact = [1] * (max_n + 1)
    inv_fact[max_n] = pow(fact[max_n], mod - 2, mod)
    for i in range(max_n - 1, -1, -1):
        inv_fact[i] = inv_fact[i+1] * (i+1) % mod
    return fact, inv_fact

def ncr(n: int, r: int, fact: list, inv_fact: list, mod: int) -> int:
    """nCr mod p in O(1) after precomputation."""
    if r < 0 or r > n: return 0
    return fact[n] * inv_fact[r] % mod * inv_fact[n-r] % mod

fact, inv_fact = precompute_factorials(1000, MOD)
print("C(10,3):", ncr(10, 3, fact, inv_fact, MOD))  # 120


# ════════════════════════════════════════════════════════════
# COMMON INTEGER TRICKS
# ════════════════════════════════════════════════════════════

def ceil_div(a: int, b: int) -> int:
    """Ceiling division without float. (a + b - 1) // b."""
    return (a + b - 1) // b

def is_perfect_square(n: int) -> bool:
    """Check if n is a perfect square. O(1)."""
    if n < 0: return False
    root = int(n**0.5)
    return root * root == n or (root+1)*(root+1) == n  # guard float imprecision

def trailing_zeros_factorial(n: int) -> int:
    """
    Count trailing zeros in n! = count pairs of (2,5) factors.
    Factors of 5 are rarer, so count factors of 5.
    n! trailing zeros = floor(n/5) + floor(n/25) + floor(n/125) + ...
    """
    count = 0
    while n >= 5:
        n //= 5
        count += n
    return count

def digit_sum(n: int) -> int:
    return sum(int(d) for d in str(abs(n)))

def is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0

def is_power_of_three(n: int) -> bool:
    """3^19 = 1162261467 is max power of 3 fitting in int."""
    return n > 0 and 1162261467 % n == 0

def count_bits(n: int) -> int:
    """Count set bits (1s) in binary representation. Brian Kernighan."""
    count = 0
    while n:
        n &= n - 1   # remove lowest set bit
        count += 1
    return count

print("Ceil(7,2):", ceil_div(7, 2))            # 4
print("Is perfect square 16:", is_perfect_square(16))  # True
print("Trailing zeros 100!:", trailing_zeros_factorial(100))  # 24
print("Digit sum 1234:", digit_sum(1234))       # 10
print("Power of 2 (16):", is_power_of_two(16)) # True
print("Power of 3 (9):", is_power_of_three(9)) # True
print("Count bits 13 (1101):", count_bits(13)) # 3


# ════════════════════════════════════════════════════════════
# FIBONACCI — Matrix Exponentiation
# ════════════════════════════════════════════════════════════

def fib_matrix(n: int, mod: int = 10**9 + 7) -> int:
    """
    Compute Fibonacci(n) in O(log n) using matrix exponentiation.
    [F(n+1)]   [1 1]^n   [F(1)]
    [F(n)  ] = [1 0]   * [F(0)]

    F(0)=0, F(1)=1
    """
    if n <= 0: return 0
    if n == 1: return 1

    def mat_mul(A, B):
        return [
            [(A[0][0]*B[0][0] + A[0][1]*B[1][0]) % mod,
             (A[0][0]*B[0][1] + A[0][1]*B[1][1]) % mod],
            [(A[1][0]*B[0][0] + A[1][1]*B[1][0]) % mod,
             (A[1][0]*B[0][1] + A[1][1]*B[1][1]) % mod],
        ]

    def mat_pow(M, p):
        if p == 1: return M
        half = mat_pow(M, p // 2)
        result = mat_mul(half, half)
        if p % 2 == 1: result = mat_mul(result, M)
        return result

    M = [[1, 1], [1, 0]]
    result = mat_pow(M, n)
    return result[0][1]   # F(n)

print("Fib(10):", fib_matrix(10))   # 55
print("Fib(50):", fib_matrix(50))   # 12586269025


# ════════════════════════════════════════════════════════════
# NUMBER PATTERNS
# ════════════════════════════════════════════════════════════

def is_happy(n: int) -> bool:
    """
    Happy number: repeatedly sum squares of digits until 1 or cycle.
    Use Floyd's cycle detection on the digit-square sequence.
    """
    def digit_square_sum(x):
        return sum(int(d)**2 for d in str(x))

    slow = fast = n
    while True:
        slow = digit_square_sum(slow)
        fast = digit_square_sum(digit_square_sum(fast))
        if slow == fast: break
    return slow == 1

print("Happy 19:", is_happy(19))  # True
print("Happy 2:", is_happy(2))    # False


# ════════════════════════════════════════════════════════════
# INTERVIEW Q&A
# ════════════════════════════════════════════════════════════
"""
Q1: What's the time complexity of the Euclidean GCD algorithm?
A: O(log min(a,b)). Each step reduces the problem size by at least half.
   Worst case: consecutive Fibonacci numbers (e.g., gcd(55,34)).

Q2: Why does Sieve of Eratosthenes start marking from i²?
A: All composite numbers j = i * k where k < i have already been marked
   by k's smaller prime factor. So we only need to start at i * i.

Q3: How does binary exponentiation work?
A: Represent exponent in binary. For each bit: square the base.
   If bit is 1, also multiply result by current base.
   Example: 3^13 = 3^8 * 3^4 * 3^1 (13 = 1101 in binary). O(log n).

Q4: When can't you use Fermat's little theorem for modular inverse?
A: When mod is NOT prime, or gcd(a, mod) ≠ 1.
   Alternative: Extended Euclidean Algorithm (works for any coprime a, mod).

Q5: How many trailing zeros in n!?
A: Count factors of 5 in n! (factors of 2 are always more plentiful):
   floor(n/5) + floor(n/25) + floor(n/125) + ... until n/5^k < 1.

Q6: Is Python immune to integer overflow?
A: Yes! Python integers are arbitrary precision (BigInt). No overflow.
   BUT: In problems requiring mod arithmetic for large numbers, you must
   still apply mod explicitly or answers will be astronomically large.

Q7: How to check if n is a perfect square safely?
A: int(n**0.5)**2 == n can fail due to float precision for large n.
   Safer: root = int(n**0.5); return root*root==n or (root+1)*(root+1)==n.

Q8: What is the Chicken McNugget theorem (Frobenius)?
A: For two coprime positive integers a,b: largest number NOT expressible
   as ax + by (x,y ≥ 0) is ab - a - b.
   Example: 3 and 5: largest non-representable = 15-3-5 = 7.

Q9: How to compute nCr without overflow (in Python)?
A: Python has no overflow. Use math.comb(n, r) directly (Python 3.8+).
   For mod: precompute factorials and inverse factorials.

Q10: What is the time complexity of prime factorization?
A: O(√n) with trial division. With Pollard's rho algorithm: O(n^(1/4)).
   For coding interviews, O(√n) is always sufficient.

Q11: How to find all divisors of n?
A: Iterate i from 1 to √n. If n%i==0, add both i and n//i.
   Total divisors = product of (exponent+1) over all prime factors.
   Example: 12 = 2²×3¹ → (2+1)(1+1) = 6 divisors.

Q12: What's the trick for quickly checking power of 2?
A: n > 0 and (n & (n-1)) == 0.
   n-1 flips all bits from the lowest set bit down. AND with n = 0 iff
   n has exactly one set bit (= power of 2).
"""
