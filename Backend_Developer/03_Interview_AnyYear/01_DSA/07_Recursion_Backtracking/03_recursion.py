# ⏰ Hour 1 — Recursion Kya Hai? (Concept)
# Recursion = function khud apne aap ko call kare

def factorial(n):
    if n == 0:
        return 1
    return n * factorial(n-1)
print(factorial(4))

# **Call Stack visually samjho:**
# ```
# factorial(4)
# └─ 4 × factorial(3)
# └─ 3 × factorial(2)
# └─ 2 × factorial(1)
# └─ 1 × factorial(0)
# └─ return 1
# └─ return 1×1 = 1
# └─ return 2×1 = 2
# └─ return 3×2 = 6
# └─ return 4×6 = 24

# 2 Cheezein HAMESHA zaroori hain

# 1. BASE CASE  — recursion kab rukegi
# 2. RECURSIVE CASE — problem choti hoti jaye

# Base case nahi → INFINITE RECURSION → crash!
def bad_func(n):
    return n * bad_func(n-1)  # ❌ kabhi nahi rukegi!
# RecursionError: maximum recursion depth exceeded


# ⏰ Hour 2 — Call Stack Samjho
import sys
print(sys.getrecursionlimit())

# Limit badhao (careful!)
sys.setrecursionlimit(1000)

# ── RECURSION vs ITERATION ──
# Iteration — loop

def factorial_loop(n):
    result = 1
    for i in range(1, n+1):
        result *= i
    return result

# Recursion — function calls

def factorial_recursion(n):
    if n == 0:
        return 1
    return n * factorial_recursion(n-1)
print(factorial_recursion(5))

# Dono same result dete hain!
print(factorial_loop(5))
print(factorial_recursion(5))

# ⏰ Hour 3 — Important Patterns
# ── PATTERN 1: Linear Recursion ──
def sum_list(arr):
    if not arr:
        return 0
    return arr[0] + sum_list(arr[1:])
print(sum_list([1, 2, 3, 4, 5]))

# ── PATTERN 2: Binary Recursion ──

def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

# ── PATTERN 3: Tail Recursion ──
def factorial_tail(n, acc=1):
    if n == 0:
        return acc
    return factorial_tail(n-1, n*acc) #last call hai

print(factorial_tail(5))

# ⏰ Hour 4 — Recursion vs Iteration Comparison
# ── FIBONACCI comparison ──
# Recursive — O(2^n) — SLOW!

def fib_slow(n):
    if n <= 1:
        return n
    return fib_slow(n-1) + fib_slow(n-2)

# Memoized — O(n) — FAST!
def fib_memo(n, memo={}):
    if n in memo: return memo[n]
    if n <= 1: return n
    memo[n] =  fib_memo(n-1, memo) + fib_memo(n-2, memo)
    return memo[n]

# # Iterative — O(n) — FASTEST!
def fib_iter(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a
print(fib_iter(10))

import time

start = time.time()
fib_slow(35)
print(f"Recursive: {time.time() - start:.2f} seconds")

start = time.time()
fib_memo(35)
print(f"Memoized: {time.time() - start:.2f} seconds")

start = time.time()
fib_iter(35)
print(f"Iterative: {time.time() - start:.2f} seconds")


# ⏰ Hour 5 — 10 Practice Problems
# Q1 — Factorial
# factorial(5) → 120

def factorial(n):
    if n == 0 or  n == 1:
        return 1
    return n * factorial(n-1)
print(factorial(5))

# Q2 — Fibonacci
# fib(10) → 55

def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)
print(fib(10))

# Q3 — Sum of list
# sum_list([1, 2, 3, 4, 5]) → 15

def sum_list(arr):
    if not arr:
        return 0
    return arr[0] + sum_list(arr[1:])
print(sum_list([1, 2, 3, 4, 5]))

# Q4 — Power (x^n)
# power(2, 10) → 1024

def power(x, n):
    if n == 0:
        return 1
    return x * power(x, n-1)
print(power(2, 10))

# Q5 — Binary search recursive
# binary_search([1,2,3,4,5,6,7,8,9], 7) → 6

def binary_search(arr, target, low=0, high=None):
    if high is None:
        high = len(arr) - 1
    if low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            return binary_search(arr, target, mid+1, high)
        else:
            return binary_search(arr, target, low, mid-1)

print(binary_search([1,2,3,4,5,6,7,8,9], 7))

# # Q6 — Reverse string recursive
# # reverse("hello") → "olleh"

def reverse_string(s):
    if not s:
        return ""
    return reverse_string(s[1:]) + s[0]
print(reverse_string("hello"))

# Q7 — Palindrome check recursive
# is_palindrome("racecar") → True
# is_palindrome("hello")   → False

def is_palindrome(s):
    if not s:
        return True
    return s[0] == s[-1] and is_palindrome(s[1:-1])
print(is_palindrome("racecar"))
print(is_palindrome("hello"))

def is_palindrome_iter(s):
    if len(s) <= 1:
        return True
    return s[0] == s[-1] and is_palindrome_iter(s[1:-1])
print(is_palindrome_iter("racecar"))

# Q8 — Sum of digits recursive
# sum_digits(1234) → 10

def sum_digits(n):
    if n < 10:
        return n
    return n % 10 + sum_digits(n // 10)
print(sum_digits(1234))

# Q9 — Tower of Hanoi
# hanoi(3, 'A', 'C', 'B')
# Output: move A→C, A→B, C→B...

def tower_of_hanoi(n, from_rod, to_rod, aux_rod):
    if n == 1:
        print(f"Move disk 1 from {from_rod} to {to_rod}")
        return
    tower_of_hanoi(n-1, from_rod, aux_rod, to_rod)
    print(f"Move disk {n} from {from_rod} to {to_rod}")
    tower_of_hanoi(n-1, aux_rod, to_rod, from_rod)

tower_of_hanoi(3, 'A', 'C', 'B')

# Q10 — Flatten nested list recursive
# flatten([1, [2, [3, [4]]], 5]) → [1,2,3,4,5]

def flatten_nested(nested_list):
    result = []
    for item in nested_list:
        if isinstance(item, list):
            result.extend(flatten_nested(item))
        else:
            result.append(item)
    return result
print(flatten_nested([1, [2, [3, [4]]], 5]))

def flatten_gen(nested):
    for item in nested:
        if isinstance(item, list):
            yield from flatten_gen(item)
        else:
            yield item

print(list(flatten_gen([1, [2, [3, [4]]], 5])))






