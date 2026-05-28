"""
╔══════════════════════════════════════════════════════════════════╗
║         RECURSION & BACKTRACKING — Complete Theory Guide         ║
╚══════════════════════════════════════════════════════════════════╝

WHAT IS RECURSION?
───────────────────
Recursion is a technique where a function calls itself to solve a
smaller version of the same problem.

Every recursive function needs:
  1. BASE CASE — condition to stop (avoids infinite recursion)
  2. RECURSIVE CASE — call self with smaller/simpler input
  3. PROGRESS — each call must move toward the base case

WHAT IS BACKTRACKING?
──────────────────────
Backtracking is a recursive technique for solving constraint satisfaction
problems by trying all possibilities and abandoning paths that violate
constraints (pruning the search tree).

Three steps in every backtracking solution:
  1. CHOOSE   — pick an option
  2. EXPLORE  — recurse with that choice
  3. UNCHOOSE — undo the choice (backtrack)

WHY USE THEM?
──────────────
- Many problems have natural recursive structure (trees, divide-and-conquer)
- Backtracking explores all solutions while pruning impossible branches
- Cleaner code than nested loops for variable-depth searches

COMPLEXITY TABLE
─────────────────────────────────────────────────────────────────
Problem Type             Time              Space
─────────────────────────────────────────────────────────────────
Fibonacci (naive)        O(2^n)            O(n) call stack
Fibonacci (memo)         O(n)              O(n)
Subsets                  O(2^n)            O(n)
Permutations             O(n!)             O(n)
Combination Sum          O(2^target)       O(target)
N-Queens                 O(n!)             O(n)
─────────────────────────────────────────────────────────────────
"""

from typing import List
from functools import lru_cache

# ─────────────────────────────────────────────
# 1. RECURSION BASICS
# ─────────────────────────────────────────────
print("=" * 60)
print("1. RECURSION FUNDAMENTALS")
print("=" * 60)

# Classic: Factorial
def factorial(n: int) -> int:
    """n! = n * (n-1) * ... * 1. Base case: 0! = 1."""
    if n <= 1:        # base case
        return 1
    return n * factorial(n - 1)  # recursive case

print(f"5! = {factorial(5)}")    # 120
print(f"0! = {factorial(0)}")    # 1

# Classic: Fibonacci — naive O(2^n) vs memoized O(n)
def fib_naive(n: int) -> int:
    if n <= 1: return n
    return fib_naive(n-1) + fib_naive(n-2)

@lru_cache(maxsize=None)
def fib_memo(n: int) -> int:
    if n <= 1: return n
    return fib_memo(n-1) + fib_memo(n-2)

print(f"fib(10) naive: {fib_naive(10)}")  # 55
print(f"fib(10) memo:  {fib_memo(10)}")   # 55

# ─────────────────────────────────────────────
# 2. THE CALL STACK
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("2. UNDERSTANDING THE CALL STACK")
print("=" * 60)

call_stack_explanation = """
When factorial(4) runs:
  factorial(4) calls factorial(3)
    factorial(3) calls factorial(2)
      factorial(2) calls factorial(1)
        factorial(1) returns 1   ← base case
      factorial(2) returns 2*1 = 2
    factorial(3) returns 3*2 = 6
  factorial(4) returns 4*6 = 24

The call stack depth = n.
Python default recursion limit ≈ 1000.
For deeper recursion: sys.setrecursionlimit(10000)
Or convert to iterative with explicit stack.
"""
print(call_stack_explanation)

# ─────────────────────────────────────────────
# 3. BACKTRACKING TEMPLATE
# ─────────────────────────────────────────────
print("=" * 60)
print("3. BACKTRACKING TEMPLATE")
print("=" * 60)

backtracking_template = '''
def backtrack(result, current, start, choices):
    # BASE CASE: Is the current state a complete solution?
    if is_complete(current):
        result.append(list(current))  # make a copy!
        return

    for choice in choices[start:]:
        # CHOOSE
        if is_valid(choice, current):
            current.append(choice)

        # EXPLORE
        backtrack(result, current, next_start, choices)

        # UNCHOOSE (backtrack)
        current.pop()
'''
print(backtracking_template)

# ─────────────────────────────────────────────
# 4. PATTERN: SUBSETS (Power Set)
# ─────────────────────────────────────────────
print("=" * 60)
print("4. PATTERN: Subsets (Power Set)")
print("=" * 60)

def subsets(nums: List[int]) -> List[List[int]]:
    """
    Generate all 2^n subsets.
    At each index, choose to include or exclude the element.
    Time: O(n * 2^n) | Space: O(n)
    """
    result = []
    def backtrack(start, current):
        result.append(list(current))  # every state is a valid subset
        for i in range(start, len(nums)):
            current.append(nums[i])       # choose
            backtrack(i + 1, current)     # explore
            current.pop()                 # unchoose
    backtrack(0, [])
    return result

print(subsets([1, 2, 3]))
# [[], [1], [1,2], [1,2,3], [1,3], [2], [2,3], [3]]

# ─────────────────────────────────────────────
# 5. PATTERN: PERMUTATIONS
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("5. PATTERN: Permutations")
print("=" * 60)

def permutations(nums: List[int]) -> List[List[int]]:
    """
    Generate all n! permutations.
    Use a 'used' set to track which elements are in current path.
    Time: O(n * n!) | Space: O(n)
    """
    result = []
    def backtrack(current, used):
        if len(current) == len(nums):
            result.append(list(current))
            return
        for i in range(len(nums)):
            if i in used:
                continue
            used.add(i)
            current.append(nums[i])        # choose
            backtrack(current, used)       # explore
            current.pop()                  # unchoose
            used.remove(i)
    backtrack([], set())
    return result

print(permutations([1, 2, 3]))
# [[1,2,3],[1,3,2],[2,1,3],[2,3,1],[3,1,2],[3,2,1]]

# ─────────────────────────────────────────────
# 6. PATTERN: COMBINATION SUM
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("6. PATTERN: Combination Sum")
print("=" * 60)

def combination_sum(candidates: List[int], target: int) -> List[List[int]]:
    """
    Find all combinations summing to target. Can reuse elements.
    Sort candidates for early termination.
    Time: O(2^target) | Space: O(target)
    """
    result = []
    def backtrack(start, current, remaining):
        if remaining == 0:
            result.append(list(current))
            return
        for i in range(start, len(candidates)):
            if candidates[i] > remaining:
                break                     # sorted → prune rest
            current.append(candidates[i]) # choose
            backtrack(i, current, remaining - candidates[i])  # can reuse i
            current.pop()                 # unchoose
    candidates.sort()
    backtrack(0, [], target)
    return result

print(combination_sum([2,3,6,7], 7))  # [[2,2,3],[7]]
print(combination_sum([2,3,5], 8))    # [[2,2,2,2],[2,3,3],[3,5]]

# ─────────────────────────────────────────────
# 7. MEMOIZATION INTRO
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("7. MEMOIZATION — Caching Recursive Results")
print("=" * 60)

"""
MEMOIZATION:
Store results of expensive function calls and return cached result
when the same inputs occur again.

When to use: Overlapping subproblems (same subproblem called multiple times).
Two ways in Python:
  1. @functools.lru_cache(maxsize=None)
  2. Manual dict cache
"""

# Manual memoization
def fib_manual_memo(n: int, memo: dict = {}) -> int:
    if n in memo:
        return memo[n]
    if n <= 1:
        return n
    memo[n] = fib_manual_memo(n-1, memo) + fib_manual_memo(n-2, memo)
    return memo[n]

# @lru_cache — cleaner
@lru_cache(maxsize=None)
def count_paths(m: int, n: int) -> int:
    """Count paths from top-left to bottom-right in m×n grid."""
    if m == 1 or n == 1:
        return 1
    return count_paths(m-1, n) + count_paths(m, n-1)

print(f"Unique paths in 3x7 grid: {count_paths(3, 7)}")  # 28

# ─────────────────────────────────────────────
# 8. RECURSION TREE VISUALIZATION
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("8. RECURSION TREE — Visualizing Complexity")
print("=" * 60)

tree_viz = """
subsets([1,2,3]) recursion tree:
              []
           /      \\
         [1]       []
        /   \\    /    \\
     [1,2] [1] [2]    []
      /         |
  [1,2,3]    [2,3]

At each level, we branch (include/exclude).
n levels → 2^n leaf nodes → O(2^n) time.

permutations([1,2,3]) recursion tree:
                  []
           /      |      \\
         [1]     [2]     [3]
        /   \\   /   \\   /   \\
     [1,2] [1,3] ...
      |
  [1,2,3]

n! leaf nodes → O(n!) time.
"""
print(tree_viz)

# ─────────────────────────────────────────────
# 9. INTERVIEW Q&A
# ─────────────────────────────────────────────
print("=" * 60)
print("INTERVIEW Q&A")
print("=" * 60)

qa = """
Q1: What's the difference between recursion and backtracking?
A1: All backtracking is recursive, but not all recursion is backtracking.
    Backtracking specifically involves UNDOING choices when a path fails.
    Regular recursion (like factorial) doesn't undo state.

Q2: When should I use backtracking vs DP?
A2: Backtracking: when you need ALL solutions, or the problem involves
    arrangement/selection (permutations, combinations, paths).
    DP: when you need ONE optimal solution and subproblems overlap.
    Key: if you only need count or optimal value → DP.
    If you need all actual solutions → backtracking.

Q3: How do you avoid duplicates in backtracking?
A3: Sort the input first. Then skip elements equal to the previous
    at the same recursion level:
    if i > start and candidates[i] == candidates[i-1]: continue

Q4: Why must you copy the current list when adding to result?
A4: result.append(current) adds a REFERENCE. When you later pop from
    current (backtrack), the appended list changes too!
    Use result.append(list(current)) or result.append(current[:]).

Q5: How do you convert deep recursion to iterative to avoid stack overflow?
A5: Use an explicit stack (list) to simulate the call stack.
    Push (state, choices) tuples and process in a loop.

Q6: What is tail recursion and does Python optimize it?
A6: Tail recursion is when the recursive call is the LAST operation.
    Python does NOT optimize tail recursion (no tail call elimination).
    Always consider iteration for tail-recursive functions in Python.

Q7: What is the time complexity of generating all subsets?
A7: O(n * 2^n) — 2^n subsets, each of average length n/2.

Q8: What is the time complexity of generating all permutations?
A8: O(n * n!) — n! permutations, each of length n.
"""
print(qa)
