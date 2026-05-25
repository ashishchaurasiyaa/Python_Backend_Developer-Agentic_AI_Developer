"""
============================================================
DIGIT DP (Digit Dynamic Programming)
============================================================

WHAT IS DIGIT DP?
-----------------
DP technique to count/find numbers in range [L, R] satisfying
some digit-based property.

WHY needed?
- Brute force O(R-L+1) is too slow when R can be 10^18
- Digit DP works in O(D * states) where D = number of digits

CLASSIC PROBLEM
---------------
"Count numbers in [L, R] whose digits sum to S"
"Count numbers in [1, N] without digit 7"
"Count numbers in [L, R] with no two same adjacent digits"

TEMPLATE
--------
Define f(N) = count of valid numbers in [0, N].
Answer for range [L, R] = f(R) - f(L-1).

Build digit-by-digit, tracking:
  - pos       : current digit position (0..D-1)
  - tight     : are we still bounded by N's digits? (if yes, can't exceed)
  - started   : have we placed a non-zero digit? (for leading zeros)
  - state     : problem-specific (e.g., digit sum so far, last digit, mask)

RECURRENCE
----------
def solve(pos, tight, started, state):
    if pos == len(digits):
        return is_valid(state)

    if (pos, tight, started, state) in memo:
        return memo[(pos, tight, started, state)]

    limit = digits[pos] if tight else 9
    total = 0
    for d in range(0, limit + 1):
        new_tight = tight and (d == limit)
        new_started = started or (d > 0)
        new_state = update(state, d, new_started)
        total += solve(pos + 1, new_tight, new_started, new_state)

    memo[(pos, tight, started, state)] = total
    return total

KEY INSIGHTS
------------
1. "tight" = upper bound flag — if true, this digit ≤ N's digit at pos
2. "started" = leading zero handling — useful for numbers with size constraints
3. Memoize only when tight=False (because tight branches are unique)
4. Convert N to digit array first

TYPICAL COMPLEXITY
------------------
O(D * 2 * 2 * S) where D ~ 18, S = state size
Usually 10^5 to 10^7 operations — very fast.

============================================================
"""
from functools import lru_cache


# ============================================================
# Template 1: Count numbers in [0, N] satisfying digit sum constraint
# ============================================================
def count_with_digit_sum(N, target_sum):
    """Count numbers in [0, N] whose digit sum equals target_sum."""
    digits = list(map(int, str(N)))
    D = len(digits)

    @lru_cache(maxsize=None)
    def dp(pos, tight, current_sum):
        if pos == D:
            return 1 if current_sum == target_sum else 0
        limit = digits[pos] if tight else 9
        total = 0
        for d in range(limit + 1):
            new_sum = current_sum + d
            if new_sum > target_sum:
                continue   # prune
            total += dp(pos + 1, tight and (d == limit), new_sum)
        return total

    return dp(0, True, 0)


# ============================================================
# Template 2: Count numbers in [0, N] without digit 'k'
# ============================================================
def count_without_digit(N, forbidden):
    digits = list(map(int, str(N)))
    D = len(digits)

    @lru_cache(maxsize=None)
    def dp(pos, tight):
        if pos == D:
            return 1
        limit = digits[pos] if tight else 9
        total = 0
        for d in range(limit + 1):
            if d == forbidden:
                continue
            total += dp(pos + 1, tight and (d == limit))
        return total

    return dp(0, True)


# ============================================================
# Template 3: Count numbers with NO two adjacent same digits
# ============================================================
def count_no_adjacent_same(N):
    digits = list(map(int, str(N)))
    D = len(digits)

    @lru_cache(maxsize=None)
    def dp(pos, tight, started, prev_digit):
        if pos == D:
            return 1 if started else 0  # 0 if we want to exclude "0"
        limit = digits[pos] if tight else 9
        total = 0
        for d in range(limit + 1):
            if started and d == prev_digit:
                continue
            new_started = started or (d > 0)
            new_prev = d if new_started else -1
            total += dp(pos + 1, tight and (d == limit), new_started, new_prev)
        # Also count "0" → just don't pass it; or count empty
        return total + (1 if pos == 0 and not started else 0) if False else total

    return dp(0, True, False, -1)


# ============================================================
# Template 4: Sum of all numbers in [0, N] (sum, not count)
# ============================================================
def sum_of_numbers_up_to(N):
    """Returns sum of all integers from 0 to N. Demonstrates DP returning value not count."""
    digits = list(map(int, str(N)))
    D = len(digits)

    @lru_cache(maxsize=None)
    def dp(pos, tight):
        if pos == D:
            return (1, 0)   # (count, sum)
        limit = digits[pos] if tight else 9
        count = 0
        total = 0
        place = 10 ** (D - pos - 1)
        for d in range(limit + 1):
            cnt, sub_sum = dp(pos + 1, tight and (d == limit))
            count += cnt
            total += sub_sum + d * place * cnt
        return count, total

    return dp(0, True)[1]


# ============================================================
# Template 5: Sum of digit sums in [0, N]
# Project Euler-style problem
# ============================================================
def sum_of_digit_sums_up_to(N):
    digits = list(map(int, str(N)))
    D = len(digits)

    @lru_cache(maxsize=None)
    def dp(pos, tight):
        if pos == D:
            return (1, 0)   # (count, total_digit_sum)
        limit = digits[pos] if tight else 9
        count = 0
        total = 0
        for d in range(limit + 1):
            cnt, sub = dp(pos + 1, tight and (d == limit))
            count += cnt
            total += sub + d * cnt
        return count, total

    return dp(0, True)[1]


# ============================================================
# Demo
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("TEMPLATE 1: Count [0, N] with digit sum == S")
    print("=" * 60)
    # In [0, 100], how many have digit sum = 5?
    # 5, 14, 23, 32, 41, 50 = 6 numbers
    print(f"  [0, 100], sum=5  : {count_with_digit_sum(100, 5)}")  # 6
    print(f"  [0, 1000], sum=5 : {count_with_digit_sum(1000, 5)}")
    print(f"  [0, 10^6], sum=10: {count_with_digit_sum(10**6, 10)}")

    print("\n" + "=" * 60)
    print("TEMPLATE 2: Count [0, N] without digit k")
    print("=" * 60)
    # [0, 100] without digit 7 → 100 - (numbers with 7)
    print(f"  [0, 100], no 7   : {count_without_digit(100, 7)}")
    print(f"  [0, 1000], no 0  : {count_without_digit(1000, 0)}")
    print(f"  [0, 10^6], no 3  : {count_without_digit(10**6, 3)}")

    print("\n" + "=" * 60)
    print("TEMPLATE 3: No adjacent same digits")
    print("=" * 60)
    print(f"  [0, 100]   : {count_no_adjacent_same(100)}")
    print(f"  [0, 1000]  : {count_no_adjacent_same(1000)}")

    print("\n" + "=" * 60)
    print("TEMPLATE 4: Sum of [0, N]")
    print("=" * 60)
    N = 100
    expected = N * (N + 1) // 2
    print(f"  sum([0, {N}])   = {sum_of_numbers_up_to(N)}  (expected {expected})")
    print(f"  sum([0, 10^5]) = {sum_of_numbers_up_to(10**5)}")

    print("\n" + "=" * 60)
    print("TEMPLATE 5: Sum of digit sums [0, N]")
    print("=" * 60)
    # Sum of digit sums [0, 12] = 0+1+2+...+9+1+2+3 = 45+1+2+3 = 51
    print(f"  [0, 12]   : {sum_of_digit_sums_up_to(12)}  (expected 51)")
    print(f"  [0, 100]  : {sum_of_digit_sums_up_to(100)}")
    print(f"  [0, 10^5] : {sum_of_digit_sums_up_to(10**5)}")

    print("\n" + "=" * 60)
    print("INTERVIEW Q&A")
    print("=" * 60)
    print("""
Q: Digit DP kab use karte ho?
A: Range [L, R] queries with digit-based property where R can be 10^18.

Q: Range [L, R] kaise handle karte?
A: solve(R) - solve(L - 1). Always reduce to [0, N] problem.

Q: 'tight' flag kya hai?
A: True = current digit bounded by N's digit at this position.
   Once we pick smaller digit, tight=False — subsequent can be 0-9.

Q: Memoization key mein 'tight' kyu?
A: Tight branches are unique per N — memoizing them across calls is wrong.
   Often we only memoize when tight=False.

Q: Complexity?
A: O(D * 2 * state_size) where D = log_10(N) ~ 18.
   State size depends on problem (digit sum, last digit, mask, etc).

Q: Common state variables?
A: position, tight flag, started flag (leading zeros),
   running sum, last digit, parity, mask of seen digits.
""")
