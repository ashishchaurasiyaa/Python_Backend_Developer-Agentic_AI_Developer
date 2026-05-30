# ── TIME COMPLEXITY (Big-O) ──
"""
Big-O = input badhne par algorithm ka kaam KAISE badhta hai (growth rate).
Constants aur lower-order terms ignore karte hain:
    O(2n + 5)  → O(n)
    O(3n^2)    → O(n^2)

Common orders (fast → slow):
    O(1)        constant      — input se farak nahi padta
    O(log n)    logarithmic   — har step me aadha kaam (binary search)
    O(n)        linear        — har element ek baar
    O(n log n)  linearithmic  — sorting (merge/heap/Tim sort)
    O(n^2)      quadratic     — same input par nested loop
    O(2^n)      exponential   — har step par branch double (naive recursion)
"""

import time


# O(1) — constant: index access, dict lookup, arithmetic
def first_element(arr):
    return arr[0] if arr else None            # ek hi step, n se independent


# O(log n) — har iteration me search space aadha
def binary_search(sorted_arr, target):
    lo, hi = 0, len(sorted_arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if sorted_arr[mid] == target:
            return mid
        if sorted_arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1


# O(n) — linear: har element ek baar touch
def sum_all(arr):
    total = 0
    for x in arr:                             # n iterations
        total += x
    return total


# O(n^2) — same input par nested loop (n*(n-1)/2 pairs)
def has_duplicates_naive(arr):
    for i in range(len(arr)):
        for j in range(i + 1, len(arr)):
            if arr[i] == arr[j]:
                return True
    return False


# O(2^n) — har call do branch banata hai (naive Fibonacci)
def fib_naive(n):
    if n < 2:
        return n
    return fib_naive(n - 1) + fib_naive(n - 2)


def _time_ms(fn, *args):
    start = time.perf_counter()
    fn(*args)
    return (time.perf_counter() - start) * 1000


if __name__ == "__main__":
    print("O(1):     first_element([10,20,30]) =", first_element([10, 20, 30]))

    data = list(range(1_000_000))
    print("O(log n): binary_search(data, 999_999) =", binary_search(data, 999_999))

    # O(n) vs O(n^2): input 2x karo, time kaise badhta hai dekho
    for n in (1000, 2000, 4000):
        worst = list(range(n))                # no duplicates → O(n^2) worst case
        print(f"n={n:<5} O(n) sum={_time_ms(sum_all, worst):7.3f}ms   "
              f"O(n^2) naive-dup={_time_ms(has_duplicates_naive, worst):8.3f}ms")

    print("O(2^n):   fib_naive(10) =", fib_naive(10))
