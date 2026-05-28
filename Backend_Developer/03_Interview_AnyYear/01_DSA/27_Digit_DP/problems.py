"""
============================================================
DIGIT DP — INTERVIEW PROBLEMS
============================================================

Problems covered:
  1. Count numbers in [L, R] with sum of digits = S (SPOJ)
  2. Numbers with unique digits (LC 357)
  3. Non-decreasing digits count
  4. Count Numbers with Repeated Digits (LC 1012)
  5. Numbers At Most N Given Digit Set (LC 902)
  6. Count "Lucky" numbers (only digits 4 and 7)
  7. Numbers divisible by K (state = remainder)
  8. Classy Numbers — at most 3 non-zero digits (CF 1036C)
  9. Count numbers in [L,R] where every digit appears at most K times
"""
from functools import lru_cache


# ============================================================
# Problem 1: Count [L, R] with digit sum = S
# ============================================================
def count_digit_sum_in_range(L, R, S):
    def f(N):
        if N < 0:
            return 0
        digits = list(map(int, str(N)))
        D = len(digits)

        @lru_cache(maxsize=None)
        def dp(pos, tight, s):
            if s > S:
                return 0
            if pos == D:
                return 1 if s == S else 0
            limit = digits[pos] if tight else 9
            total = 0
            for d in range(limit + 1):
                total += dp(pos + 1, tight and (d == limit), s + d)
            return total
        return dp(0, True, 0)

    return f(R) - f(L - 1)


# ============================================================
# Problem 2: Count Numbers with Unique Digits (LC 357)
# ============================================================
def count_unique_digits(n):
    """Count x in [0, 10^n) where all digits are unique."""
    if n == 0:
        return 1
    N = 10 ** n - 1
    digits = list(map(int, str(N)))
    D = len(digits)

    @lru_cache(maxsize=None)
    def dp(pos, tight, started, mask):
        if pos == D:
            return 1
        limit = digits[pos] if tight else 9
        total = 0
        for d in range(limit + 1):
            if started and (mask >> d) & 1:
                continue
            new_started = started or (d > 0)
            new_mask = mask | (1 << d) if new_started else 0
            total += dp(pos + 1, tight and (d == limit), new_started, new_mask)
        return total

    return dp(0, True, False, 0)


# ============================================================
# Problem 3: Count non-decreasing digit numbers in [0, N]
# Example: 1234, 1199, 222 — yes; 132 — no
# ============================================================
def count_non_decreasing(N):
    digits = list(map(int, str(N)))
    D = len(digits)

    @lru_cache(maxsize=None)
    def dp(pos, tight, prev):
        if pos == D:
            return 1
        limit = digits[pos] if tight else 9
        total = 0
        for d in range(limit + 1):
            if d < prev:
                continue
            total += dp(pos + 1, tight and (d == limit), d)
        return total
    return dp(0, True, 0)


# ============================================================
# Problem 4: Count Numbers with Repeated Digits (LC 1012)
# ============================================================
def count_with_repeated_digits(N):
    total = N
    no_repeat = count_unique_in_range(N)
    return total - no_repeat + 1   # +1 if we counted 0 differently


def count_unique_in_range(N):
    """Count numbers in [1, N] with all distinct digits."""
    if N == 0:
        return 0
    digits = list(map(int, str(N)))
    D = len(digits)

    @lru_cache(maxsize=None)
    def dp(pos, tight, started, mask):
        if pos == D:
            return 1 if started else 0
        limit = digits[pos] if tight else 9
        total = 0
        for d in range(limit + 1):
            if started and (mask >> d) & 1:
                continue
            new_started = started or (d > 0)
            new_mask = mask | (1 << d) if new_started else 0
            total += dp(pos + 1, tight and (d == limit), new_started, new_mask)
        return total
    return dp(0, True, False, 0)


# ============================================================
# Problem 5: Numbers At Most N Given Digit Set (LC 902)
# Given digit set D = {'1','3','5','7'}, count x in [1, N]
# using ONLY these digits.
# ============================================================
def at_most_n_given_digits(digit_set, N):
    digits = list(map(int, str(N)))
    D = len(digits)
    allowed = set(int(d) for d in digit_set)

    @lru_cache(maxsize=None)
    def dp(pos, tight, started):
        if pos == D:
            return 1 if started else 0
        limit = digits[pos] if tight else 9
        total = 0
        for d in range(limit + 1):
            if d > 0 and d not in allowed:
                continue
            if d == 0 and not started:
                # leading zero — keep started=False
                total += dp(pos + 1, tight and (d == limit), False)
            elif d in allowed:
                total += dp(pos + 1, tight and (d == limit), True)
        return total
    return dp(0, True, False)


# ============================================================
# Problem 6: Lucky Numbers (only digits 4 and 7)
# How many in [1, N]?
# ============================================================
def count_lucky(N):
    digits = list(map(int, str(N)))
    D = len(digits)

    @lru_cache(maxsize=None)
    def dp(pos, tight, started):
        if pos == D:
            return 1 if started else 0
        limit = digits[pos] if tight else 9
        total = 0
        for d in range(limit + 1):
            if d == 0 and not started:
                total += dp(pos + 1, tight and (d == limit), False)
            elif d in (4, 7):
                total += dp(pos + 1, tight and (d == limit), True)
        return total
    return dp(0, True, False)


# ============================================================
# Problem 7: Numbers divisible by K in [0, N]
# State: remainder modulo K
# ============================================================
def count_divisible_by(N, K):
    digits = list(map(int, str(N)))
    D = len(digits)

    @lru_cache(maxsize=None)
    def dp(pos, tight, rem):
        if pos == D:
            return 1 if rem == 0 else 0
        limit = digits[pos] if tight else 9
        total = 0
        for d in range(limit + 1):
            new_rem = (rem * 10 + d) % K
            total += dp(pos + 1, tight and (d == limit), new_rem)
        return total
    return dp(0, True, 0)


# ============================================================
# Problem 8: Classy Numbers (CF 1036C)
# Numbers with at most 3 non-zero digits in [L, R]
# ============================================================
def count_classy(L, R):
    def f(N):
        if N < 0:
            return 0
        digits = list(map(int, str(N)))
        D = len(digits)

        @lru_cache(maxsize=None)
        def dp(pos, tight, non_zero_count):
            if non_zero_count > 3:
                return 0
            if pos == D:
                return 1
            limit = digits[pos] if tight else 9
            total = 0
            for d in range(limit + 1):
                new_nz = non_zero_count + (1 if d > 0 else 0)
                total += dp(pos + 1, tight and (d == limit), new_nz)
            return total
        return dp(0, True, 0)
    return f(R) - f(L - 1)


# ============================================================
# Problem 9: Every digit appears at most K times
# ============================================================
def count_max_digit_freq(N, K):
    """In [0, N], count numbers where every digit appears ≤ K times."""
    digits = list(map(int, str(N)))
    D = len(digits)

    # State: count of each digit so far
    @lru_cache(maxsize=None)
    def dp(pos, tight, freq_tuple):
        if pos == D:
            return 1
        limit = digits[pos] if tight else 9
        total = 0
        freq = list(freq_tuple)
        for d in range(limit + 1):
            if freq[d] >= K:
                continue
            freq[d] += 1
            total += dp(pos + 1, tight and (d == limit), tuple(freq))
            freq[d] -= 1
        return total
    return dp(0, True, tuple([0] * 10))


# ============================================================
# Demo
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("PROBLEM 1: Digit sum in range")
    print("=" * 60)
    print(f"  [1, 100], sum=10  : {count_digit_sum_in_range(1, 100, 10)}")  # 9
    print(f"  [1, 1000], sum=5  : {count_digit_sum_in_range(1, 1000, 5)}")

    print("\n" + "=" * 60)
    print("PROBLEM 2: Unique digits (LC 357)")
    print("=" * 60)
    for n in range(1, 5):
        print(f"  n={n}: {count_unique_digits(n)}")

    print("\n" + "=" * 60)
    print("PROBLEM 3: Non-decreasing digit numbers")
    print("=" * 60)
    print(f"  [0, 100]   : {count_non_decreasing(100)}")
    print(f"  [0, 1000]  : {count_non_decreasing(1000)}")

    print("\n" + "=" * 60)
    print("PROBLEM 5: At Most N with digit set (LC 902)")
    print("=" * 60)
    print(f"  digits=['1','3','5','7'], N=100 : {at_most_n_given_digits({'1','3','5','7'}, 100)}")

    print("\n" + "=" * 60)
    print("PROBLEM 6: Lucky numbers (digits 4 and 7)")
    print("=" * 60)
    print(f"  [1, 100]   : {count_lucky(100)}")  # 4,7,44,47,74,77 = 6
    print(f"  [1, 1000]  : {count_lucky(1000)}")

    print("\n" + "=" * 60)
    print("PROBLEM 7: Divisible by K")
    print("=" * 60)
    print(f"  [0, 100], K=7  : {count_divisible_by(100, 7)}")   # 15 (0,7,14,...,98)
    print(f"  [0, 1000], K=13: {count_divisible_by(1000, 13)}")

    print("\n" + "=" * 60)
    print("PROBLEM 8: Classy numbers (≤ 3 non-zero digits)")
    print("=" * 60)
    print(f"  [1, 1000]  : {count_classy(1, 1000)}")
    print(f"  [1, 10^9]  : {count_classy(1, 10**9)}")

    print("\n" + "=" * 60)
    print("PROBLEM 9: Each digit at most K times")
    print("=" * 60)
    print(f"  [0, 1000], K=1  : {count_max_digit_freq(1000, 1)}")
    print(f"  [0, 10000], K=2 : {count_max_digit_freq(10000, 2)}")

    print("\n" + "=" * 60)
    print("PATTERN SUMMARY")
    print("=" * 60)
    print("""
Common state extensions:
  - digit sum so far
  - last digit (for adjacent constraints)
  - bitmask of digits seen (uniqueness)
  - count of specific digit (frequency limit)
  - running remainder (divisibility)
  - count of non-zero digits
  - parity / odd-even

Always: pos, tight, started + problem-specific state.
""")
