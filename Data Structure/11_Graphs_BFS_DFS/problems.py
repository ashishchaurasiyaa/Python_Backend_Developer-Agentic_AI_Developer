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

print("\n✓ All 12 Graph BFS/DFS problems solved!")
