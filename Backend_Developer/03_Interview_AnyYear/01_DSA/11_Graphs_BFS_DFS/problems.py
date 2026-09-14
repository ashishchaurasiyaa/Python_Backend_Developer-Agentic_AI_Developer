"""
╔══════════════════════════════════════════════════════════════════╗
║           GRAPHS BFS & DFS — 12 LeetCode-Style Problems          ║
╚══════════════════════════════════════════════════════════════════╝
"""

from typing import List, Optional, Dict
from collections import deque, defaultdict

# ══════════════════════════════════════════════════════════════════
# Problem 1: Number of Islands (LC 200)
# ══════════════════════════════════════════════════════════════════
def numIslands(grid: List[List[str]]) -> int:
    """
    Count the number of islands (groups of connected '1's).

    Approach: DFS from each unvisited '1'. Mark all connected '1's as '0'.

    Example:
      [["1","1","0"],["0","1","0"],["0","0","1"]] → 2
    """
    if not grid: return 0
    rows, cols = len(grid), len(grid[0])
    count = 0

    def dfs(r, c):
        if r < 0 or r >= rows or c < 0 or c >= cols or grid[r][c] != '1':
            return
        grid[r][c] = '0'  # mark visited
        dfs(r+1,c); dfs(r-1,c); dfs(r,c+1); dfs(r,c-1)

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == '1':
                dfs(r, c)
                count += 1
    return count

print("=== Number of Islands ===")
grid = [["1","1","0","0","0"],["1","1","0","0","0"],["0","0","1","0","0"],["0","0","0","1","1"]]
print(numIslands(grid))  # 3
# Time: O(m*n) | Space: O(m*n) stack

# ══════════════════════════════════════════════════════════════════
# Problem 2: Clone Graph (LC 133)
# ══════════════════════════════════════════════════════════════════
class Node:
    def __init__(self, val=0, neighbors=None):
        self.val = val
        self.neighbors = neighbors if neighbors is not None else []

def cloneGraph(node: Optional[Node]) -> Optional[Node]:
    """
    Deep clone a connected undirected graph.

    Approach: BFS/DFS with a hashmap old_node → clone.
    When we clone a node, clone its neighbors too.

    Example: Graph 1-2-3-4-1 (square) → cloned square
    """
    if not node: return None
    old_to_new = {}

    def dfs(node):
        if node in old_to_new:
            return old_to_new[node]
        clone = Node(node.val)
        old_to_new[node] = clone
        for neighbor in node.neighbors:
            clone.neighbors.append(dfs(neighbor))
        return clone

    return dfs(node)

print("\n=== Clone Graph ===")
n1 = Node(1); n2 = Node(2); n3 = Node(3); n4 = Node(4)
n1.neighbors = [n2, n4]; n2.neighbors = [n1, n3]
n3.neighbors = [n2, n4]; n4.neighbors = [n1, n3]
cloned = cloneGraph(n1)
print(f"Original n1 id: {id(n1)}, Clone id: {id(cloned)}, Clone val: {cloned.val}")
# Time: O(V + E) | Space: O(V)

# ══════════════════════════════════════════════════════════════════
# Problem 3: Pacific Atlantic Water Flow (LC 417)
# ══════════════════════════════════════════════════════════════════
def pacificAtlantic(heights: List[List[int]]) -> List[List[int]]:
    """
    Water flows from higher/equal to lower. Find cells that can reach
    both the Pacific (top/left) and Atlantic (bottom/right) oceans.

    Approach: Reverse — do BFS/DFS from ocean borders inward.
    Cells reachable from Pacific ∩ cells reachable from Atlantic = answer.

    Example: [[1,2,2,3,5],[3,2,3,4,4],[2,4,5,3,1],[6,7,1,4,5],[5,1,1,2,4]]
    → [[0,4],[1,3],[1,4],[2,2],[3,0],[3,1],[4,0]]
    """
    rows, cols = len(heights), len(heights[0])
    pacific = set(); atlantic = set()

    def dfs(r, c, visited, prev_height):
        if (r,c) in visited or r<0 or r>=rows or c<0 or c>=cols:
            return
        if heights[r][c] < prev_height:
            return
        visited.add((r,c))
        for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
            dfs(r+dr, c+dc, visited, heights[r][c])

    for r in range(rows):
        dfs(r, 0, pacific, heights[r][0])          # left border → Pacific
        dfs(r, cols-1, atlantic, heights[r][cols-1])  # right border → Atlantic
    for c in range(cols):
        dfs(0, c, pacific, heights[0][c])          # top border → Pacific
        dfs(rows-1, c, atlantic, heights[rows-1][c])  # bottom → Atlantic

    return [[r,c] for r in range(rows) for c in range(cols) if (r,c) in pacific and (r,c) in atlantic]

print("\n=== Pacific Atlantic Water Flow ===")
heights = [[1,2,2,3,5],[3,2,3,4,4],[2,4,5,3,1],[6,7,1,4,5],[5,1,1,2,4]]
print(pacificAtlantic(heights))
# Time: O(m*n) | Space: O(m*n)

# ══════════════════════════════════════════════════════════════════
# Problem 4: Surrounded Regions (LC 130)
# ══════════════════════════════════════════════════════════════════
def solve(board: List[List[str]]) -> None:
    """
    Capture all 'O's surrounded by 'X' (not touching any border).

    Approach: BFS/DFS from border 'O's. Mark all reachable 'O's as safe ('T').
    Then flip all remaining 'O's to 'X', and 'T' back to 'O'.

    Example: [["X","X","X","X"],["X","O","O","X"],["X","X","O","X"],["X","O","X","X"]]
    → [["X","X","X","X"],["X","X","X","X"],["X","X","X","X"],["X","O","X","X"]]
    """
    if not board: return
    rows, cols = len(board), len(board[0])

    def dfs(r, c):
        if r<0 or r>=rows or c<0 or c>=cols or board[r][c] != 'O':
            return
        board[r][c] = 'T'  # temporarily mark as safe
        dfs(r+1,c); dfs(r-1,c); dfs(r,c+1); dfs(r,c-1)

    # Mark all border-connected 'O's as safe
    for r in range(rows):
        dfs(r, 0); dfs(r, cols-1)
    for c in range(cols):
        dfs(0, c); dfs(rows-1, c)

    # Flip: remaining 'O' → 'X', 'T' → 'O'
    for r in range(rows):
        for c in range(cols):
            if board[r][c] == 'O': board[r][c] = 'X'
            elif board[r][c] == 'T': board[r][c] = 'O'

print("\n=== Surrounded Regions ===")
board = [["X","X","X","X"],["X","O","O","X"],["X","X","O","X"],["X","O","X","X"]]
solve(board)
print(board)
# Time: O(m*n) | Space: O(m*n)

# ══════════════════════════════════════════════════════════════════
# Problem 5: Rotting Oranges (LC 994)
# ══════════════════════════════════════════════════════════════════
def orangesRotting(grid: List[List[int]]) -> int:
    """
    0=empty, 1=fresh, 2=rotten. Rotten spreads to adjacent fresh each minute.
    Return time to rot all, or -1 if impossible.

    Approach: Multi-source BFS from all rotten oranges simultaneously.

    Example: [[2,1,1],[1,1,0],[0,1,1]] → 4
    """
    rows, cols = len(grid), len(grid[0])
    queue = deque()
    fresh = 0

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 2: queue.append((r, c, 0))
            elif grid[r][c] == 1: fresh += 1

    if fresh == 0: return 0
    max_time = 0

    while queue:
        r, c, t = queue.popleft()
        for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
            nr, nc = r+dr, c+dc
            if 0<=nr<rows and 0<=nc<cols and grid[nr][nc] == 1:
                grid[nr][nc] = 2
                fresh -= 1
                max_time = max(max_time, t+1)
                queue.append((nr, nc, t+1))

    return max_time if fresh == 0 else -1

print("\n=== Rotting Oranges ===")
print(orangesRotting([[2,1,1],[1,1,0],[0,1,1]]))  # 4
print(orangesRotting([[2,1,1],[0,1,1],[1,0,1]])) # -1
# Time: O(m*n) | Space: O(m*n)

# ══════════════════════════════════════════════════════════════════
# Problem 6: Walls and Gates (LC 286)
# ══════════════════════════════════════════════════════════════════
def wallsAndGates(rooms: List[List[int]]) -> None:
    """
    Fill each empty room with distance to nearest gate.
    INF=empty, -1=wall, 0=gate.

    Approach: Multi-source BFS from all gates simultaneously.

    Example: [[INF,-1,0,INF],[INF,INF,INF,-1],[INF,-1,INF,-1],[0,-1,INF,INF]]
    → [[3,-1,0,1],[2,2,1,-1],[1,-1,2,-1],[0,-1,3,4]]
    """
    INF = float('inf')
    rows, cols = len(rooms), len(rooms[0])
    queue = deque()

    for r in range(rows):
        for c in range(cols):
            if rooms[r][c] == 0:
                queue.append((r, c))

    while queue:
        r, c = queue.popleft()
        for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
            nr, nc = r+dr, c+dc
            if 0<=nr<rows and 0<=nc<cols and rooms[nr][nc] == INF:
                rooms[nr][nc] = rooms[r][c] + 1
                queue.append((nr, nc))

print("\n=== Walls and Gates ===")
INF = float('inf')
rooms = [[INF,-1,0,INF],[INF,INF,INF,-1],[INF,-1,INF,-1],[0,-1,INF,INF]]
wallsAndGates(rooms)
for row in rooms: print(row)
# Time: O(m*n) | Space: O(m*n)

# ══════════════════════════════════════════════════════════════════
# Problem 7: Course Schedule (LC 207) — Cycle Detection
# ══════════════════════════════════════════════════════════════════
def canFinish(numCourses: int, prerequisites: List[List[int]]) -> bool:
    """
    Can you finish all courses? (No circular dependency)
    = Detect if directed graph has a cycle.

    Approach: DFS with visiting set (in current path = cycle).
    0=unvisited, 1=visiting, 2=done.

    Example:
      numCourses=2, prerequisites=[[1,0]] → True
      numCourses=2, prerequisites=[[1,0],[0,1]] → False
    """
    graph = defaultdict(list)
    for a, b in prerequisites:
        graph[b].append(a)  # b must be taken before a

    visited = [0] * numCourses  # 0=unvisited, 1=visiting, 2=done

    def dfs(node):
        if visited[node] == 1: return False  # cycle!
        if visited[node] == 2: return True   # already processed
        visited[node] = 1
        for neighbor in graph[node]:
            if not dfs(neighbor): return False
        visited[node] = 2
        return True

    for i in range(numCourses):
        if not dfs(i): return False
    return True

print("\n=== Course Schedule ===")
print(canFinish(2, [[1,0]]))      # True
print(canFinish(2, [[1,0],[0,1]])) # False
# Time: O(V + E) | Space: O(V + E)

# ══════════════════════════════════════════════════════════════════
# Problem 8: Course Schedule II (LC 210) — Topological Sort
# ══════════════════════════════════════════════════════════════════
def findOrder(numCourses: int, prerequisites: List[List[int]]) -> List[int]:
    """
    Return a valid order to take courses. Return [] if impossible (cycle).
    = Topological sort of directed graph.

    Approach: Kahn's BFS algorithm.
    Find all nodes with in-degree 0. Process them, reducing in-degrees.

    Example:
      numCourses=4, prerequisites=[[1,0],[2,0],[3,1],[3,2]] → [0,1,2,3]
    """
    graph = defaultdict(list)
    in_degree = [0] * numCourses
    for a, b in prerequisites:
        graph[b].append(a)
        in_degree[a] += 1

    queue = deque([i for i in range(numCourses) if in_degree[i] == 0])
    order = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return order if len(order) == numCourses else []

print("\n=== Course Schedule II ===")
print(findOrder(2, [[1,0]]))                                 # [0,1]
print(findOrder(4, [[1,0],[2,0],[3,1],[3,2]]))               # [0,1,2,3] or [0,2,1,3]
print(findOrder(2, [[1,0],[0,1]]))                           # []
# Time: O(V + E) | Space: O(V + E)

# ══════════════════════════════════════════════════════════════════
# Problem 9: Number of Connected Components (LC 323)
# ══════════════════════════════════════════════════════════════════
def countComponents(n: int, edges: List[List[int]]) -> int:
    """
    Given n nodes (0 to n-1) and undirected edges, count connected components.

    Approach: DFS from each unvisited node. Count DFS calls.

    Example:
      n=5, edges=[[0,1],[1,2],[3,4]] → 2
      n=5, edges=[[0,1],[1,2],[2,3],[3,4]] → 1
    """
    graph = defaultdict(list)
    for u, v in edges:
        graph[u].append(v)
        graph[v].append(u)

    visited = set()
    count = 0

    def dfs(node):
        visited.add(node)
        for neighbor in graph[node]:
            if neighbor not in visited:
                dfs(neighbor)

    for node in range(n):
        if node not in visited:
            dfs(node)
            count += 1
    return count

print("\n=== Number of Connected Components ===")
print(countComponents(5, [[0,1],[1,2],[3,4]]))         # 2
print(countComponents(5, [[0,1],[1,2],[2,3],[3,4]]))   # 1
# Time: O(V + E) | Space: O(V + E)

# ══════════════════════════════════════════════════════════════════
# Problem 10: Graph Valid Tree (LC 261)
# ══════════════════════════════════════════════════════════════════
def validTree(n: int, edges: List[List[int]]) -> bool:
    """
    Determine if n nodes and given edges form a valid tree.
    Valid tree: connected AND no cycles.
    Equivalent: n-1 edges AND connected.

    Approach: DFS — check no cycle and all nodes visited.

    Example:
      n=5, edges=[[0,1],[0,2],[0,3],[1,4]] → True
      n=5, edges=[[0,1],[1,2],[2,3],[1,3],[1,4]] → False (cycle)
    """
    if len(edges) != n - 1: return False  # quick check
    graph = defaultdict(list)
    for u, v in edges:
        graph[u].append(v)
        graph[v].append(u)

    visited = set()
    def dfs(node, parent):
        visited.add(node)
        for neighbor in graph[node]:
            if neighbor == parent: continue
            if neighbor in visited: return False
            if not dfs(neighbor, node): return False
        return True

    return dfs(0, -1) and len(visited) == n

print("\n=== Graph Valid Tree ===")
print(validTree(5, [[0,1],[0,2],[0,3],[1,4]]))            # True
print(validTree(5, [[0,1],[1,2],[2,3],[1,3],[1,4]]))      # False
# Time: O(V + E) | Space: O(V + E)

# ══════════════════════════════════════════════════════════════════
# Problem 11: Word Ladder (LC 127)
# ══════════════════════════════════════════════════════════════════
def ladderLength(beginWord: str, endWord: str, wordList: List[str]) -> int:
    """
    Find shortest transformation sequence from beginWord to endWord.
    Each step changes one letter. Each intermediate word must be in wordList.

    Approach: BFS. Each word's neighbors = all words differing by one letter.
    Optimization: Group words by pattern (h*t → hot, hat, hit).

    Example:
      beginWord="hit", endWord="cog", wordList=["hot","dot","dog","lot","log","cog"]
      → 5 ("hit"→"hot"→"dot"→"dog"→"cog")
    """
    word_set = set(wordList)
    if endWord not in word_set: return 0

    # Build adjacency list by pattern
    neighbors = defaultdict(list)
    all_words = wordList + [beginWord]
    for word in all_words:
        for i in range(len(word)):
            pattern = word[:i] + '*' + word[i+1:]
            neighbors[pattern].append(word)

    visited = {beginWord}
    queue = deque([(beginWord, 1)])

    while queue:
        word, length = queue.popleft()
        if word == endWord: return length
        for i in range(len(word)):
            pattern = word[:i] + '*' + word[i+1:]
            for neighbor in neighbors[pattern]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, length + 1))

    return 0

print("\n=== Word Ladder ===")
print(ladderLength("hit","cog",["hot","dot","dog","lot","log","cog"]))  # 5
print(ladderLength("hit","cog",["hot","dot","dog","lot","log"]))        # 0
# Time: O(n * m²) | Space: O(n * m²)

# ══════════════════════════════════════════════════════════════════
# Problem 12: Alien Dictionary (LC 269)
# ══════════════════════════════════════════════════════════════════
def alienOrder(words: List[str]) -> str:
    """
    Given a sorted list of words in an alien language, find the character order.
    Return any valid ordering, or "" if invalid (cycle).

    Approach:
    1. Compare adjacent words to extract ordering constraints.
    2. Topological sort (Kahn's BFS) on character graph.

    Example:
      ["wrt","wrf","er","ett","rftt"] → "wertf"
      ["z","x"] → "zx"
      ["z","x","z"] → "" (z > x > z = cycle)
    """
    # Initialize graph with all unique characters
    graph = {c: set() for word in words for c in word}
    in_degree = {c: 0 for c in graph}

    # Extract ordering from adjacent words
    for i in range(len(words) - 1):
        w1, w2 = words[i], words[i+1]
        min_len = min(len(w1), len(w2))
        if len(w1) > len(w2) and w1[:min_len] == w2[:min_len]:
            return ""  # invalid: prefix word comes after longer word
        for j in range(min_len):
            if w1[j] != w2[j]:
                if w2[j] not in graph[w1[j]]:
                    graph[w1[j]].add(w2[j])
                    in_degree[w2[j]] += 1
                break

    # Kahn's BFS topological sort
    queue = deque([c for c in in_degree if in_degree[c] == 0])
    result = []
    while queue:
        c = queue.popleft()
        result.append(c)
        for neighbor in graph[c]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return ''.join(result) if len(result) == len(graph) else ""

print("\n=== Alien Dictionary ===")
print(alienOrder(["wrt","wrf","er","ett","rftt"]))  # "wertf" or valid topo order
print(alienOrder(["z","x"]))                         # "zx"
print(alienOrder(["z","x","z"]))                     # ""
# Time: O(C) where C = total chars | Space: O(1) — 26 chars at most

# ── Shared TreeNode class (for tree-based BFS/DFS problems below) ────
class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

# ══════════════════════════════════════════════════════════════════
# Problem 13: Symmetric Tree (LC 101)
# ══════════════════════════════════════════════════════════════════
def isSymmetric(root: Optional[TreeNode]) -> bool:
    """
    Check whether a binary tree is a mirror of itself around its center.

    Approach: BFS with a queue holding pairs of nodes to compare.
    Push (left, right) of each pair; they must match value-for-value,
    and left.left must mirror right.right, left.right mirror right.left.

    Example:
      [1,2,2,3,4,4,3] → True
      [1,2,2,None,3,None,3] → False
    """
    if not root: return True
    queue = deque([(root.left, root.right)])
    while queue:
        left, right = queue.popleft()
        if not left and not right: continue
        if not left or not right or left.val != right.val: return False
        queue.append((left.left, right.right))
        queue.append((left.right, right.left))
    return True

print("\n=== Symmetric Tree ===")
t1 = TreeNode(1, TreeNode(2, TreeNode(3), TreeNode(4)), TreeNode(2, TreeNode(4), TreeNode(3)))
print(isSymmetric(t1))  # True
t2 = TreeNode(1, TreeNode(2, None, TreeNode(3)), TreeNode(2, None, TreeNode(3)))
print(isSymmetric(t2))  # False
# Time: O(n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 14: Binary Tree Zigzag Level Order Traversal (LC 103)
# ══════════════════════════════════════════════════════════════════
def zigzagLevelOrder(root: Optional[TreeNode]) -> List[List[int]]:
    """
    Return level-order traversal, alternating left-to-right and right-to-left.

    Approach: Standard BFS level by level; reverse alternate levels.

    Example:
      [3,9,20,None,None,15,7] → [[3],[20,9],[15,7]]
    """
    if not root: return []
    result = []
    queue = deque([root])
    left_to_right = True

    while queue:
        level = []
        for _ in range(len(queue)):
            node = queue.popleft()
            level.append(node.val)
            if node.left: queue.append(node.left)
            if node.right: queue.append(node.right)
        result.append(level if left_to_right else level[::-1])
        left_to_right = not left_to_right

    return result

print("\n=== Binary Tree Zigzag Level Order Traversal ===")
t3 = TreeNode(3, TreeNode(9), TreeNode(20, TreeNode(15), TreeNode(7)))
print(zigzagLevelOrder(t3))  # [[3],[20,9],[15,7]]
# Time: O(n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 15: Maximum Width of Binary Tree (LC 662)
# ══════════════════════════════════════════════════════════════════
def widthOfBinaryTree(root: Optional[TreeNode]) -> int:
    """
    Find the maximum width (number of slots between leftmost and rightmost
    non-null nodes at any level, counting nulls in between).

    Approach: BFS level-order, numbering each node as if the tree were a
    complete binary tree (index i → children 2i, 2i+1). Width of a level
    = last_index - first_index + 1.

    Example:
      [1,3,2,5,3,None,9] → 4
    """
    if not root: return 0
    max_width = 0
    queue = deque([(root, 0)])

    while queue:
        level_size = len(queue)
        _, first_idx = queue[0]
        last_idx = first_idx
        for _ in range(level_size):
            node, idx = queue.popleft()
            last_idx = idx
            if node.left: queue.append((node.left, 2*idx))
            if node.right: queue.append((node.right, 2*idx + 1))
        max_width = max(max_width, last_idx - first_idx + 1)

    return max_width

print("\n=== Maximum Width of Binary Tree ===")
t4 = TreeNode(1, TreeNode(3, TreeNode(5), TreeNode(3)), TreeNode(2, None, TreeNode(9)))
print(widthOfBinaryTree(t4))  # 4
# Time: O(n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 16: Flood Fill (LC 733)
# ══════════════════════════════════════════════════════════════════
def floodFill(image: List[List[int]], sr: int, sc: int, color: int) -> List[List[int]]:
    """
    Starting from (sr, sc), replace the connected region of the same color
    (4-directionally) with the new color.

    Approach: DFS from the start pixel, flood-filling matching neighbors.

    Example:
      image=[[1,1,1],[1,1,0],[1,0,1]], sr=1, sc=1, color=2
      → [[2,2,2],[2,2,0],[2,0,1]]
    """
    rows, cols = len(image), len(image[0])
    start_color = image[sr][sc]
    if start_color == color: return image

    def dfs(r, c):
        if r < 0 or r >= rows or c < 0 or c >= cols or image[r][c] != start_color:
            return
        image[r][c] = color
        dfs(r+1,c); dfs(r-1,c); dfs(r,c+1); dfs(r,c-1)

    dfs(sr, sc)
    return image

print("\n=== Flood Fill ===")
print(floodFill([[1,1,1],[1,1,0],[1,0,1]], 1, 1, 2))  # [[2,2,2],[2,2,0],[2,0,1]]
# Time: O(m*n) | Space: O(m*n)

# ══════════════════════════════════════════════════════════════════
# Problem 17: Bus Routes (LC 815)
# ══════════════════════════════════════════════════════════════════
def numBusesToDestination(routes: List[List[int]], source: int, target: int) -> int:
    """
    Each routes[i] is the sequence of stops bus i visits (in a loop).
    Return the minimum number of buses to ride from source to target.

    Approach: BFS over BUSES (not stops). Build stop → list of buses
    serving that stop. BFS from source stop; at each step "take" every
    unvisited bus reachable from the current stop, then enqueue all
    stops on those buses.

    Example:
      routes=[[1,2,7],[3,6,7]], source=1, target=6 → 2
    """
    if source == target: return 0

    stop_to_buses = defaultdict(list)
    for bus, route in enumerate(routes):
        for stop in route:
            stop_to_buses[stop].append(bus)

    visited_buses = set()
    visited_stops = {source}
    queue = deque([(source, 0)])

    while queue:
        stop, buses_taken = queue.popleft()
        for bus in stop_to_buses[stop]:
            if bus in visited_buses: continue
            visited_buses.add(bus)
            for next_stop in routes[bus]:
                if next_stop == target: return buses_taken + 1
                if next_stop not in visited_stops:
                    visited_stops.add(next_stop)
                    queue.append((next_stop, buses_taken + 1))

    return -1

print("\n=== Bus Routes ===")
print(numBusesToDestination([[1,2,7],[3,6,7]], 1, 6))  # 2
print(numBusesToDestination([[1,2,7],[3,6,7]], 1, 1))  # 0
# Time: O(sum of route lengths) | Space: O(sum of route lengths)

# ══════════════════════════════════════════════════════════════════
# Problem 18: All Nodes Distance K in Binary Tree (LC 863)
# ══════════════════════════════════════════════════════════════════
def distanceK(root: TreeNode, target: TreeNode, k: int) -> List[int]:
    """
    Return the values of all nodes that are exactly distance k from
    the target node (distance in edges; tree treated as an undirected
    graph, so paths may go up through parents too).

    Approach: 1) DFS to build a child → parent map.
              2) BFS from target, treating left/right/parent as neighbors.

    Example:
      tree=[3,5,1,6,2,0,8,None,None,7,4], target=5, k=2 → [7,4,1]
    """
    parent = {}

    def build_parents(node, par):
        if not node: return
        parent[node] = par
        build_parents(node.left, node)
        build_parents(node.right, node)

    build_parents(root, None)

    visited = {target}
    queue = deque([(target, 0)])
    result = []

    while queue:
        node, dist = queue.popleft()
        if dist == k:
            result.append(node.val)
            continue
        for neighbor in (node.left, node.right, parent[node]):
            if neighbor and neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, dist + 1))

    return result

print("\n=== All Nodes Distance K in Binary Tree ===")
n7, n4 = TreeNode(7), TreeNode(4)
n6, n2 = TreeNode(6), TreeNode(2, n7, n4)
n0, n8 = TreeNode(0), TreeNode(8)
n5 = TreeNode(5, n6, n2)
n1 = TreeNode(1, n0, n8)
root5 = TreeNode(3, n5, n1)
print(sorted(distanceK(root5, n5, 2)))  # [1, 4, 7]
# Time: O(n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 19: Shortest Path to Get Food (LC 1730)
# ══════════════════════════════════════════════════════════════════
def getFood(grid: List[List[str]]) -> int:
    """
    Grid cells: '*' = your position, '#' = food, 'O' = free space,
    'X' = obstacle. Return the shortest number of steps to reach any
    food cell, or -1 if impossible.

    Approach: BFS from the starting '*' cell, stepping only onto
    'O' or '#' cells, stopping as soon as a '#' is reached.

    Example:
      grid=[["X","X","X","X","X","X"],
            ["X","*","O","O","O","X"],
            ["X","O","O","#","O","X"],
            ["X","X","X","X","X","X"]] → 3
    """
    rows, cols = len(grid), len(grid[0])
    start = None
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == '*':
                start = (r, c)
                break
        if start: break

    queue = deque([(start[0], start[1], 0)])
    visited = {start}

    while queue:
        r, c, steps = queue.popleft()
        if grid[r][c] == '#':
            return steps
        for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
            nr, nc = r+dr, c+dc
            if (0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in visited
                    and grid[nr][nc] != 'X'):
                visited.add((nr, nc))
                queue.append((nr, nc, steps + 1))

    return -1

print("\n=== Shortest Path to Get Food ===")
grid_food = [["X","X","X","X","X","X"],
             ["X","*","O","O","O","X"],
             ["X","O","O","#","O","X"],
             ["X","X","X","X","X","X"]]
print(getFood(grid_food))  # 3
# Time: O(m*n) | Space: O(m*n)

print("\n✓ All 19 Graph BFS/DFS problems solved!")
