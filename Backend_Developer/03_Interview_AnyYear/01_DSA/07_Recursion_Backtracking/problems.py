"""
╔══════════════════════════════════════════════════════════════════╗
║       RECURSION & BACKTRACKING — 12 LeetCode-Style Problems      ║
╚══════════════════════════════════════════════════════════════════╝
"""

from typing import List, Optional

# ══════════════════════════════════════════════════════════════════
# Problem 1: Subsets (LC 78)
# ══════════════════════════════════════════════════════════════════
def subsets(nums: List[int]) -> List[List[int]]:
    """
    Return all possible subsets (power set). No duplicates in input.

    Approach: At each index, choose include or exclude.
    Every recursion state is a valid subset.

    Example:
      [1,2,3] → [[],[1],[1,2],[1,2,3],[1,3],[2],[2,3],[3]]
    """
    result = []
    def backtrack(start, current):
        result.append(list(current))
        for i in range(start, len(nums)):
            current.append(nums[i])
            backtrack(i + 1, current)
            current.pop()
    backtrack(0, [])
    return result

print("=== Subsets ===")
print(subsets([1,2,3]))
# Time: O(n * 2^n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 2: Subsets II (LC 90) — with duplicates
# ══════════════════════════════════════════════════════════════════
def subsetsWithDup(nums: List[int]) -> List[List[int]]:
    """
    Return all unique subsets. Input may contain duplicates.

    Approach: Sort first. Skip elements equal to previous at the same
    recursion level (i > start and nums[i] == nums[i-1]).

    Example:
      [1,2,2] → [[],[1],[1,2],[1,2,2],[2],[2,2]]
    """
    nums.sort()
    result = []
    def backtrack(start, current):
        result.append(list(current))
        for i in range(start, len(nums)):
            if i > start and nums[i] == nums[i-1]:
                continue  # skip duplicate at same level
            current.append(nums[i])
            backtrack(i + 1, current)
            current.pop()
    backtrack(0, [])
    return result

print("\n=== Subsets II (with duplicates) ===")
print(subsetsWithDup([1,2,2]))
# Time: O(n * 2^n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 3: Permutations (LC 46)
# ══════════════════════════════════════════════════════════════════
def permute(nums: List[int]) -> List[List[int]]:
    """
    Return all possible permutations of distinct integers.

    Approach: Track which indices are used. At each level, try
    every unused element.

    Example:
      [1,2,3] → [[1,2,3],[1,3,2],[2,1,3],[2,3,1],[3,1,2],[3,2,1]]
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
            current.append(nums[i])
            backtrack(current, used)
            current.pop()
            used.remove(i)
    backtrack([], set())
    return result

print("\n=== Permutations ===")
print(permute([1,2,3]))
# Time: O(n * n!) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 4: Combination Sum (LC 39)
# ══════════════════════════════════════════════════════════════════
def combinationSum(candidates: List[int], target: int) -> List[List[int]]:
    """
    Find all unique combinations summing to target. Can reuse elements.

    Approach: Sort for pruning. Pass same index i (not i+1) to allow reuse.

    Example:
      candidates=[2,3,6,7], target=7 → [[2,2,3],[7]]
      candidates=[2,3,5], target=8 → [[2,2,2,2],[2,3,3],[3,5]]
    """
    candidates.sort()
    result = []
    def backtrack(start, current, remaining):
        if remaining == 0:
            result.append(list(current))
            return
        for i in range(start, len(candidates)):
            if candidates[i] > remaining:
                break  # sorted → prune
            current.append(candidates[i])
            backtrack(i, current, remaining - candidates[i])  # reuse i
            current.pop()
    backtrack(0, [], target)
    return result

print("\n=== Combination Sum ===")
print(combinationSum([2,3,6,7], 7))  # [[2,2,3],[7]]
# Time: O(2^target) | Space: O(target)

# ══════════════════════════════════════════════════════════════════
# Problem 5: Combination Sum II (LC 40)
# ══════════════════════════════════════════════════════════════════
def combinationSum2(candidates: List[int], target: int) -> List[List[int]]:
    """
    Find all unique combinations summing to target. Each number used once.
    Input may have duplicates.

    Approach: Sort. Skip duplicates at same level. Pass i+1 (no reuse).

    Example:
      candidates=[10,1,2,7,6,1,5], target=8 → [[1,1,6],[1,2,5],[1,7],[2,6]]
      candidates=[2,5,2,1,2], target=5 → [[1,2,2],[5]]
    """
    candidates.sort()
    result = []
    def backtrack(start, current, remaining):
        if remaining == 0:
            result.append(list(current))
            return
        for i in range(start, len(candidates)):
            if candidates[i] > remaining:
                break
            if i > start and candidates[i] == candidates[i-1]:
                continue  # skip duplicates at same level
            current.append(candidates[i])
            backtrack(i + 1, current, remaining - candidates[i])
            current.pop()
    backtrack(0, [], target)
    return result

print("\n=== Combination Sum II ===")
print(combinationSum2([10,1,2,7,6,1,5], 8))  # [[1,1,6],[1,2,5],[1,7],[2,6]]
# Time: O(2^n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 6: Word Search (LC 79)
# ══════════════════════════════════════════════════════════════════
def exist(board: List[List[str]], word: str) -> bool:
    """
    Find if word exists in the grid by moving adjacent (4-directional) cells.
    The same cell cannot be used twice.

    Approach: DFS/backtracking from each cell. Mark visited by modifying
    the cell, then restore it (backtrack).

    Example:
      board=[["A","B","C","E"],["S","F","C","S"],["A","D","E","E"]]
      word="ABCCED" → True
      word="SEE" → True
      word="ABCB" → False
    """
    rows, cols = len(board), len(board[0])

    def dfs(r, c, idx):
        if idx == len(word):
            return True
        if r < 0 or r >= rows or c < 0 or c >= cols or board[r][c] != word[idx]:
            return False
        # Mark visited
        temp = board[r][c]
        board[r][c] = '#'
        # Explore all 4 directions
        found = (dfs(r+1, c, idx+1) or dfs(r-1, c, idx+1) or
                 dfs(r, c+1, idx+1) or dfs(r, c-1, idx+1))
        # Restore (backtrack)
        board[r][c] = temp
        return found

    for r in range(rows):
        for c in range(cols):
            if dfs(r, c, 0):
                return True
    return False

print("\n=== Word Search ===")
board = [["A","B","C","E"],["S","F","C","S"],["A","D","E","E"]]
print(exist(board, "ABCCED"))  # True
print(exist(board, "SEE"))     # True
print(exist(board, "ABCB"))    # False
# Time: O(m*n * 4^len(word)) | Space: O(len(word))

# ══════════════════════════════════════════════════════════════════
# Problem 7: N-Queens (LC 51)
# ══════════════════════════════════════════════════════════════════
def solveNQueens(n: int) -> List[List[str]]:
    """
    Place n queens on an n×n chessboard such that no two queens attack each other.
    Return all distinct solutions.

    Approach: Place one queen per row. Track occupied columns and diagonals.
    Use sets: cols, diag1 (r-c), diag2 (r+c) for O(1) conflict check.

    Example:
      n=4 → [[".Q..","...Q","Q...","..Q."],["..Q.","Q...","...Q",".Q.."]]
    """
    result = []
    cols = set()
    diag1 = set()  # top-left to bottom-right: r - c constant
    diag2 = set()  # top-right to bottom-left: r + c constant

    board = [['.' ] * n for _ in range(n)]

    def backtrack(row):
        if row == n:
            result.append([''.join(r) for r in board])
            return
        for col in range(n):
            if col in cols or (row - col) in diag1 or (row + col) in diag2:
                continue
            # Place queen
            cols.add(col); diag1.add(row-col); diag2.add(row+col)
            board[row][col] = 'Q'
            backtrack(row + 1)
            # Remove queen (backtrack)
            cols.remove(col); diag1.remove(row-col); diag2.remove(row+col)
            board[row][col] = '.'

    backtrack(0)
    return result

print("\n=== N-Queens ===")
solutions = solveNQueens(4)
print(f"Number of solutions for n=4: {len(solutions)}")  # 2
for sol in solutions:
    print(sol)
# Time: O(n!) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 8: Palindrome Partitioning (LC 131)
# ══════════════════════════════════════════════════════════════════
def partition(s: str) -> List[List[str]]:
    """
    Partition s such that every substring is a palindrome. Return all partitions.

    Approach: Backtracking. At each position, try all substrings from start.
    If palindrome, recurse on the remainder.

    Example:
      "aab" → [["a","a","b"],["aa","b"]]
      "a" → [["a"]]
    """
    result = []
    def is_palindrome(sub):
        return sub == sub[::-1]

    def backtrack(start, current):
        if start == len(s):
            result.append(list(current))
            return
        for end in range(start + 1, len(s) + 1):
            sub = s[start:end]
            if is_palindrome(sub):
                current.append(sub)
                backtrack(end, current)
                current.pop()

    backtrack(0, [])
    return result

print("\n=== Palindrome Partitioning ===")
print(partition("aab"))  # [["a","a","b"],["aa","b"]]
print(partition("a"))    # [["a"]]
# Time: O(n * 2^n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 9: Letter Combinations of a Phone Number (LC 17)
# ══════════════════════════════════════════════════════════════════
def letterCombinations(digits: str) -> List[str]:
    """
    Given a string of digits 2-9, return all possible letter combinations
    (like old phone keypad).

    Approach: Backtracking. At each digit, try all its mapped letters.

    Example:
      "23" → ["ad","ae","af","bd","be","bf","cd","ce","cf"]
      "" → []
    """
    if not digits:
        return []
    phone = {
        '2': 'abc', '3': 'def', '4': 'ghi', '5': 'jkl',
        '6': 'mno', '7': 'pqrs', '8': 'tuv', '9': 'wxyz'
    }
    result = []
    def backtrack(idx, current):
        if idx == len(digits):
            result.append(current)
            return
        for ch in phone[digits[idx]]:
            backtrack(idx + 1, current + ch)
    backtrack(0, "")
    return result

print("\n=== Letter Combinations of Phone Number ===")
print(letterCombinations("23"))  # ["ad","ae","af","bd","be","bf","cd","ce","cf"]
print(letterCombinations(""))    # []
# Time: O(4^n * n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 10: Generate Parentheses (LC 22)
# ══════════════════════════════════════════════════════════════════
def generateParenthesis(n: int) -> List[str]:
    """
    Generate all combinations of n pairs of well-formed parentheses.

    Approach: Backtracking with open_count and close_count.
    - Can add '(' if open < n
    - Can add ')' if close < open

    Example:
      n=3 → ["((()))","(()())","(())()","()(())","()()()"]
    """
    result = []
    def backtrack(s, open_cnt, close_cnt):
        if len(s) == 2 * n:
            result.append(s)
            return
        if open_cnt < n:
            backtrack(s + '(', open_cnt + 1, close_cnt)
        if close_cnt < open_cnt:
            backtrack(s + ')', open_cnt, close_cnt + 1)
    backtrack("", 0, 0)
    return result

print("\n=== Generate Parentheses ===")
print(generateParenthesis(3))
print(f"Count for n=4: {len(generateParenthesis(4))}")  # 14
# Time: O(4^n / sqrt(n)) — Catalan number | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 11: Sudoku Solver (LC 37)
# ══════════════════════════════════════════════════════════════════
def solveSudoku(board: List[List[str]]) -> None:
    """
    Solve a Sudoku puzzle in-place. Empty cells are '.'.
    Rules: each row, column, and 3×3 box contains digits 1-9 exactly once.

    Approach: Backtracking. Find empty cell, try digits 1-9,
    check validity, recurse. If fails, reset and try next.

    Example: Given a valid sudoku with some cells as '.', fills them in.
    """
    def is_valid(r, c, num):
        # Check row
        if num in board[r]:
            return False
        # Check column
        if num in [board[i][c] for i in range(9)]:
            return False
        # Check 3x3 box
        box_r, box_c = 3 * (r // 3), 3 * (c // 3)
        for i in range(box_r, box_r + 3):
            for j in range(box_c, box_c + 3):
                if board[i][j] == num:
                    return False
        return True

    def solve():
        for r in range(9):
            for c in range(9):
                if board[r][c] == '.':
                    for num in '123456789':
                        if is_valid(r, c, num):
                            board[r][c] = num
                            if solve():
                                return True
                            board[r][c] = '.'  # backtrack
                    return False  # no valid digit found
        return True  # all cells filled

    solve()

print("\n=== Sudoku Solver ===")
board = [
    ["5","3",".",".","7",".",".",".","."],
    ["6",".",".","1","9","5",".",".","."],
    [".","9","8",".",".",".",".","6","."],
    ["8",".",".",".","6",".",".",".","3"],
    ["4",".",".","8",".","3",".",".","1"],
    ["7",".",".",".","2",".",".",".","6"],
    [".","6",".",".",".",".","2","8","."],
    [".",".",".","4","1","9",".",".","5"],
    [".",".",".",".","8",".",".","7","9"]
]
solveSudoku(board)
for row in board:
    print(row)
# Time: O(9^(81)) worst case but pruning makes it fast | Space: O(81)

# ══════════════════════════════════════════════════════════════════
# Problem 12: Path Sum II (LC 113)
# ══════════════════════════════════════════════════════════════════
class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

def pathSum(root: Optional[TreeNode], targetSum: int) -> List[List[int]]:
    """
    Find all root-to-leaf paths where the sum equals targetSum.

    Approach: DFS backtracking. Track current path and remaining sum.
    At leaf, if remaining == 0, record path.

    Example:
      Tree: 5→[4→[11→[7,2]],8→[13,4→[5,1]]], targetSum=22
      → [[5,4,11,2],[5,8,4,5]]
    """
    result = []
    def dfs(node, remaining, path):
        if not node:
            return
        path.append(node.val)
        if not node.left and not node.right and remaining == node.val:
            result.append(list(path))  # leaf with matching sum
        else:
            dfs(node.left, remaining - node.val, path)
            dfs(node.right, remaining - node.val, path)
        path.pop()  # backtrack

    dfs(root, targetSum, [])
    return result

print("\n=== Path Sum II ===")
# Build tree: 5 -> [4->[11->[7,2]], 8->[13, 4->[5,1]]]
root = TreeNode(5)
root.left = TreeNode(4)
root.right = TreeNode(8)
root.left.left = TreeNode(11)
root.left.left.left = TreeNode(7)
root.left.left.right = TreeNode(2)
root.right.left = TreeNode(13)
root.right.right = TreeNode(4)
root.right.right.left = TreeNode(5)
root.right.right.right = TreeNode(1)
print(pathSum(root, 22))  # [[5,4,11,2],[5,8,4,5]]
# Time: O(n²) | Space: O(n)

print("\n✓ All 12 Recursion & Backtracking problems solved!")
