"""
20 — Matrix / 2D Grid — Theory
================================
Level: Intermediate
"""
from __future__ import annotations
from typing import List, Tuple
from collections import deque

# ════════════════════════════════════════════════════════════
# WHAT & WHY
# ════════════════════════════════════════════════════════════
"""
MATRIX = 2D array [rows][cols].
Most problems treat it as a GRAPH where each cell is a node,
and edges go to adjacent cells (4-directional or 8-directional).

COMMON PROBLEM TYPES:
  1. Traversal (BFS/DFS on grid)
  2. Island counting / flood fill
  3. Shortest path in grid
  4. Matrix transformation (rotate, spiral, transpose)
  5. Dynamic programming on grid
  6. Binary search on sorted matrix
"""

# ════════════════════════════════════════════════════════════
# COMPLEXITY
# ════════════════════════════════════════════════════════════
"""
Operation                    Time        Space
──────────────────────────────────────────────
BFS / DFS traversal          O(m×n)      O(m×n)
Rotate matrix in-place       O(m×n)      O(1)
Spiral traversal             O(m×n)      O(1)
Search in sorted matrix      O(log(m×n)) O(1)
Flood fill                   O(m×n)      O(m×n)
Shortest path (BFS)          O(m×n)      O(m×n)
DP on grid                   O(m×n)      O(m×n) or O(n)
"""

# ════════════════════════════════════════════════════════════
# DIRECTIONS — 4-directional and 8-directional
# ════════════════════════════════════════════════════════════

DIRS_4 = [(0,1),(0,-1),(1,0),(-1,0)]               # right, left, down, up
DIRS_8 = [(0,1),(0,-1),(1,0),(-1,0),
           (1,1),(1,-1),(-1,1),(-1,-1)]             # includes diagonals

def in_bounds(r: int, c: int, rows: int, cols: int) -> bool:
    return 0 <= r < rows and 0 <= c < cols


# ════════════════════════════════════════════════════════════
# PATTERN 1: BFS on Grid (Shortest Path)
# ════════════════════════════════════════════════════════════

def bfs_shortest_path(grid: List[List[int]], start: Tuple, end: Tuple) -> int:
    """
    Shortest path from start to end on binary grid (0=open, 1=blocked).
    Returns number of steps, or -1 if unreachable.
    """
    rows, cols = len(grid), len(grid[0])
    sr, sc = start
    er, ec = end
    if grid[sr][sc] == 1 or grid[er][ec] == 1:
        return -1

    visited = [[False]*cols for _ in range(rows)]
    visited[sr][sc] = True
    queue = deque([(sr, sc, 0)])   # (row, col, distance)

    while queue:
        r, c, dist = queue.popleft()
        if r == er and c == ec:
            return dist
        for dr, dc in DIRS_4:
            nr, nc = r+dr, c+dc
            if in_bounds(nr, nc, rows, cols) and not visited[nr][nc] and grid[nr][nc] == 0:
                visited[nr][nc] = True
                queue.append((nr, nc, dist+1))
    return -1


# ════════════════════════════════════════════════════════════
# PATTERN 2: DFS / Flood Fill
# ════════════════════════════════════════════════════════════

def num_islands(grid: List[List[str]]) -> int:
    """
    Count number of islands (group of '1's connected 4-directionally).
    DFS flood fill: mark visited cells as '0'.
    O(m×n) time.
    """
    if not grid: return 0
    rows, cols = len(grid), len(grid[0])
    count = 0

    def dfs(r, c):
        if not in_bounds(r, c, rows, cols) or grid[r][c] != '1':
            return
        grid[r][c] = '0'   # mark visited (in-place)
        for dr, dc in DIRS_4:
            dfs(r+dr, c+dc)

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == '1':
                dfs(r, c)
                count += 1
    return count

grid = [['1','1','0'],['0','1','0'],['0','0','1']]
print("Islands:", num_islands(grid))   # 2


# ════════════════════════════════════════════════════════════
# PATTERN 3: Multi-source BFS (0-1 matrix, rotting oranges)
# ════════════════════════════════════════════════════════════

def multi_source_bfs(grid: List[List[int]]) -> List[List[int]]:
    """
    Distance from nearest 0 for each cell (LC 542: 0-1 Matrix).
    Start BFS from ALL zeros simultaneously.
    """
    rows, cols = len(grid), len(grid[0])
    dist = [[float('inf')]*cols for _ in range(rows)]
    queue = deque()

    # Seed all zeros
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 0:
                dist[r][c] = 0
                queue.append((r, c))

    while queue:
        r, c = queue.popleft()
        for dr, dc in DIRS_4:
            nr, nc = r+dr, c+dc
            if in_bounds(nr, nc, rows, cols) and dist[nr][nc] > dist[r][c] + 1:
                dist[nr][nc] = dist[r][c] + 1
                queue.append((nr, nc))
    return dist

print("0-1 matrix:", multi_source_bfs([[0,0,0],[0,1,0],[1,1,1]]))


# ════════════════════════════════════════════════════════════
# PATTERN 4: Matrix Rotation (90° clockwise in-place)
# ════════════════════════════════════════════════════════════

def rotate_90_clockwise(matrix: List[List[int]]) -> None:
    """
    Rotate n×n matrix 90° clockwise IN-PLACE.
    Step 1: Transpose (swap matrix[i][j] and matrix[j][i])
    Step 2: Reverse each row.
    O(n²) time, O(1) space.
    """
    n = len(matrix)
    # Transpose
    for i in range(n):
        for j in range(i+1, n):
            matrix[i][j], matrix[j][i] = matrix[j][i], matrix[i][j]
    # Reverse each row
    for row in matrix:
        row.reverse()

m = [[1,2,3],[4,5,6],[7,8,9]]
rotate_90_clockwise(m)
print("Rotated 90°:", m)   # [[7,4,1],[8,5,2],[9,6,3]]


# ════════════════════════════════════════════════════════════
# PATTERN 5: Spiral Traversal
# ════════════════════════════════════════════════════════════

def spiral_order(matrix: List[List[int]]) -> List[int]:
    """
    Traverse matrix in spiral order.
    4 boundaries: top, bottom, left, right — shrink after each pass.
    O(m×n) time, O(1) extra space.
    """
    result = []
    if not matrix: return result
    top, bottom = 0, len(matrix) - 1
    left, right = 0, len(matrix[0]) - 1

    while top <= bottom and left <= right:
        for c in range(left, right+1):    result.append(matrix[top][c])
        top += 1
        for r in range(top, bottom+1):   result.append(matrix[r][right])
        right -= 1
        if top <= bottom:
            for c in range(right, left-1, -1): result.append(matrix[bottom][c])
            bottom -= 1
        if left <= right:
            for r in range(bottom, top-1, -1): result.append(matrix[r][left])
            left += 1
    return result

print("Spiral:", spiral_order([[1,2,3],[4,5,6],[7,8,9]]))  # [1,2,3,6,9,8,7,4,5]


# ════════════════════════════════════════════════════════════
# PATTERN 6: Search in Sorted Matrix
# ════════════════════════════════════════════════════════════

def search_matrix(matrix: List[List[int]], target: int) -> bool:
    """
    LC 74: Each row sorted, first element of row > last of previous.
    Binary search treating matrix as flat sorted array.
    O(log(m×n)).
    """
    rows, cols = len(matrix), len(matrix[0])
    lo, hi = 0, rows * cols - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        val = matrix[mid // cols][mid % cols]
        if val == target:   return True
        elif val < target:  lo = mid + 1
        else:               hi = mid - 1
    return False

def search_matrix_ii(matrix: List[List[int]], target: int) -> bool:
    """
    LC 240: Each row and column sorted independently.
    Start from top-right. Go left if too big, down if too small.
    O(m + n).
    """
    if not matrix: return False
    r, c = 0, len(matrix[0]) - 1
    while r < len(matrix) and c >= 0:
        if matrix[r][c] == target:   return True
        elif matrix[r][c] > target:  c -= 1
        else:                        r += 1
    return False

print("Search matrix:", search_matrix([[1,3,5,7],[10,11,16,20],[23,30,34,60]], 3))  # True
print("Search matrix II:", search_matrix_ii([[1,4,7],[2,5,8],[3,6,9]], 5))  # True


# ════════════════════════════════════════════════════════════
# PATTERN 7: DP on Grid
# ════════════════════════════════════════════════════════════

def unique_paths(m: int, n: int) -> int:
    """Number of unique paths from top-left to bottom-right (right/down moves only)."""
    dp = [[1]*n for _ in range(m)]
    for r in range(1, m):
        for c in range(1, n):
            dp[r][c] = dp[r-1][c] + dp[r][c-1]
    return dp[m-1][n-1]

def min_path_sum(grid: List[List[int]]) -> int:
    """Minimum sum path from top-left to bottom-right."""
    rows, cols = len(grid), len(grid[0])
    dp = [[0]*cols for _ in range(rows)]
    dp[0][0] = grid[0][0]
    for c in range(1, cols): dp[0][c] = dp[0][c-1] + grid[0][c]
    for r in range(1, rows): dp[r][0] = dp[r-1][0] + grid[r][0]
    for r in range(1, rows):
        for c in range(1, cols):
            dp[r][c] = grid[r][c] + min(dp[r-1][c], dp[r][c-1])
    return dp[rows-1][cols-1]

print("Unique paths 3×7:", unique_paths(3, 7))   # 28
print("Min path sum:", min_path_sum([[1,3,1],[1,5,1],[4,2,1]]))  # 7


# ════════════════════════════════════════════════════════════
# PATTERN 8: Set Zeros (in-place marker trick)
# ════════════════════════════════════════════════════════════

def set_zeroes(matrix: List[List[int]]) -> None:
    """
    If cell is 0, set entire row and column to 0. In-place O(1) space.
    Use first row and first column as markers.
    """
    rows, cols = len(matrix), len(matrix[0])
    first_row_zero = any(matrix[0][c] == 0 for c in range(cols))
    first_col_zero = any(matrix[r][0] == 0 for r in range(rows))

    # Use first row/col as flags
    for r in range(1, rows):
        for c in range(1, cols):
            if matrix[r][c] == 0:
                matrix[r][0] = 0
                matrix[0][c] = 0

    # Zero out based on flags
    for r in range(1, rows):
        for c in range(1, cols):
            if matrix[r][0] == 0 or matrix[0][c] == 0:
                matrix[r][c] = 0

    if first_row_zero:
        for c in range(cols): matrix[0][c] = 0
    if first_col_zero:
        for r in range(rows): matrix[r][0] = 0


# ════════════════════════════════════════════════════════════
# INTERVIEW Q&A
# ════════════════════════════════════════════════════════════
"""
Q1: BFS vs DFS for grid problems — when to use which?
A: BFS → shortest path, minimum steps (guarantees level-by-level exploration).
   DFS → connectivity, flood fill, island detection (simpler code, less memory
   for sparse graphs). For shortest path in unweighted grid, always BFS.

Q2: How to handle visited cells without extra space?
A: Modify grid in-place: mark visited cells with a sentinel ('0', -1, '#').
   Restore if needed (backtracking). Trade-off: mutates input.

Q3: What is multi-source BFS and when to use it?
A: Start BFS from multiple source cells simultaneously. Used when you need
   distance from the nearest source (not a specific source).
   Examples: 0-1 Matrix, Rotting Oranges, Walls and Gates.

Q4: How to rotate a matrix 90° counter-clockwise?
A: Transpose then reverse each COLUMN (or: reverse each row then transpose).
   Clockwise = transpose + reverse rows. Counter-clockwise = transpose + reverse cols.

Q5: How to search in a row-and-column sorted matrix in O(m+n)?
A: Start at top-right corner. If target < current → move left. If target > current → move down.
   At each step, eliminate one row or one column. Total: O(m+n).

Q6: What is the island problem and what are its variants?
A: Count connected components of '1' in binary grid.
   Variants: max island area (LC 695), perimeter (LC 463), distinct islands (LC 694),
   number of enclaves (LC 1020), making large island (LC 827).

Q7: How does the spiral traversal work?
A: Maintain 4 boundaries (top, bottom, left, right). Each full loop: traverse right
   (shrink top), down (shrink right), left (shrink bottom), up (shrink left).
   Stop when boundaries cross. O(m×n) time, O(1) space.

Q8: How to detect a cycle in a grid?
A: DFS with visited array. Track parent cell to avoid false cycles.
   For directed: use color states (white=unvisited, gray=in-stack, black=done).

Q9: What is the "walls and gates" pattern?
A: Multi-source BFS from all gates (value 0) simultaneously.
   Fills distance to nearest gate for all empty rooms (INF cells).
   One BFS pass instead of BFS from each gate separately.

Q10: How to handle diagonal movement in grid BFS?
A: Use DIRS_8 = 8 directions. Note: diagonal distance = Chebyshev distance.
   For Euclidean distance approximation: cost of diagonal = √2 ≈ 1.414.
   For integer cost: diagonal = 1 (same as cardinal) or use weighted BFS.
"""
