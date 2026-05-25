"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DSA — Graphs: BFS, DFS, Topological Sort, Union-Find, Dijkstra
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from collections import deque, defaultdict
import heapq


# ─────────────────────────────────────────────────────────────────────────────
# 1. GRAPH REPRESENTATIONS
# ─────────────────────────────────────────────────────────────────────────────

# --- Adjacency List ---
# Space: O(V + E)
# Best for sparse graphs (most real-world graphs)

def build_adjacency_list(edges, n):
    """Build undirected graph adjacency list from edge list."""
    graph = defaultdict(list)
    for u, v in edges:
        graph[u].append(v)
        graph[v].append(u)
    return graph

# Example:
# edges = [(0,1),(0,2),(1,3)]
# graph[0] = [1, 2]
# graph[1] = [0, 3]
# graph[2] = [0]
# graph[3] = [1]


# --- Adjacency Matrix ---
# Space: O(V^2)
# Best for dense graphs, O(1) edge lookup

def build_adjacency_matrix(edges, n):
    """Build undirected graph adjacency matrix."""
    matrix = [[0] * n for _ in range(n)]
    for u, v in edges:
        matrix[u][v] = 1
        matrix[v][u] = 1
    return matrix


# ─────────────────────────────────────────────────────────────────────────────
# 2. BFS TEMPLATE
# ─────────────────────────────────────────────────────────────────────────────
# Time: O(V + E)   Space: O(V)

def bfs(graph, start):
    """Standard BFS traversal returning visit order."""
    visited = set([start])
    queue = deque([start])
    order = []

    while queue:
        node = queue.popleft()
        order.append(node)

        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return order


# ─────────────────────────────────────────────────────────────────────────────
# 3. DFS TEMPLATES
# ─────────────────────────────────────────────────────────────────────────────

# --- Recursive DFS ---
# Time: O(V + E)   Space: O(V) call stack

def dfs_recursive(graph, node, visited=None):
    """Recursive DFS traversal."""
    if visited is None:
        visited = set()
    visited.add(node)
    for neighbor in graph[node]:
        if neighbor not in visited:
            dfs_recursive(graph, neighbor, visited)
    return visited


# --- Iterative DFS ---
# Time: O(V + E)   Space: O(V)

def dfs_iterative(graph, start):
    """Iterative DFS using explicit stack."""
    visited = set()
    stack = [start]
    order = []

    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        order.append(node)
        for neighbor in graph[node]:
            if neighbor not in visited:
                stack.append(neighbor)

    return order


# ─────────────────────────────────────────────────────────────────────────────
# 4. NUMBER OF ISLANDS (Grid BFS/DFS)
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 200
# Time: O(m * n)   Space: O(m * n)

def numIslands(grid):
    """
    Count number of islands in a 2D grid.
    '1' = land, '0' = water.
    BFS floods each unvisited land cell.
    """
    if not grid:
        return 0

    rows, cols = len(grid), len(grid[0])
    visited = set()
    count = 0

    def bfs(r, c):
        queue = deque()
        queue.append((r, c))
        visited.add((r, c))
        while queue:
            row, col = queue.popleft()
            directions = [(1,0),(-1,0),(0,1),(0,-1)]
            for dr, dc in directions:
                nr, nc = row + dr, col + dc
                if (0 <= nr < rows and 0 <= nc < cols
                        and grid[nr][nc] == '1'
                        and (nr, nc) not in visited):
                    visited.add((nr, nc))
                    queue.append((nr, nc))

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == '1' and (r, c) not in visited:
                bfs(r, c)
                count += 1

    return count


# Test
grid1 = [
    ["1","1","0","0","0"],
    ["1","1","0","0","0"],
    ["0","0","1","0","0"],
    ["0","0","0","1","1"]
]
print("Number of Islands:", numIslands(grid1))   # Expected: 3


# ─────────────────────────────────────────────────────────────────────────────
# 5. CLONE GRAPH
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 133
# Time: O(V + E)   Space: O(V)

class GraphNode:
    def __init__(self, val=0, neighbors=None):
        self.val = val
        self.neighbors = neighbors if neighbors is not None else []


def cloneGraph(node):
    """
    Deep clone a connected undirected graph.
    BFS approach: map from original node -> clone node.
    """
    if not node:
        return None

    cloned = {}          # original_node -> cloned_node
    queue = deque([node])
    cloned[node] = GraphNode(node.val)

    while queue:
        curr = queue.popleft()
        for neighbor in curr.neighbors:
            if neighbor not in cloned:
                cloned[neighbor] = GraphNode(neighbor.val)
                queue.append(neighbor)
            cloned[curr].neighbors.append(cloned[neighbor])

    return cloned[node]


# ─────────────────────────────────────────────────────────────────────────────
# 6. COURSE SCHEDULE — CYCLE DETECTION (Kahn's Algorithm / BFS Topological Sort)
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 207
# Time: O(V + E)   Space: O(V + E)

def canFinish(numCourses, prerequisites):
    """
    Determine if all courses can be finished (no cycle in directed graph).
    Uses Kahn's BFS topological sort: if all nodes are processed -> no cycle.

    State:
    - in_degree[i] = number of prerequisites for course i
    - When in_degree becomes 0, course can be taken (add to queue)
    """
    in_degree = [0] * numCourses
    adj = defaultdict(list)

    for course, prereq in prerequisites:
        adj[prereq].append(course)
        in_degree[course] += 1

    # Start with all courses that have no prerequisites
    queue = deque([i for i in range(numCourses) if in_degree[i] == 0])
    completed = 0

    while queue:
        course = queue.popleft()
        completed += 1
        for next_course in adj[course]:
            in_degree[next_course] -= 1
            if in_degree[next_course] == 0:
                queue.append(next_course)

    return completed == numCourses


# Test
print("Can Finish:", canFinish(2, [[1,0]]))          # True
print("Can Finish:", canFinish(2, [[1,0],[0,1]]))     # False (cycle)


# ─────────────────────────────────────────────────────────────────────────────
# 7. TOPOLOGICAL SORT
# ─────────────────────────────────────────────────────────────────────────────
# Time: O(V + E)   Space: O(V + E)

# --- DFS-based Topological Sort ---
def topological_sort_dfs(n, edges):
    """
    DFS-based topological sort using finish-time ordering.
    Nodes are added to result AFTER all their descendants are visited.
    Reverse the result at the end.
    """
    adj = defaultdict(list)
    for u, v in edges:
        adj[u].append(v)

    visited = set()
    result = []

    def dfs(node):
        visited.add(node)
        for neighbor in adj[node]:
            if neighbor not in visited:
                dfs(neighbor)
        result.append(node)   # append after all descendants

    for i in range(n):
        if i not in visited:
            dfs(i)

    return result[::-1]   # reverse to get topological order


# --- BFS / Kahn's Algorithm ---
def topological_sort_kahn(n, edges):
    """
    Kahn's BFS topological sort.
    Repeatedly remove nodes with in-degree 0.
    """
    in_degree = [0] * n
    adj = defaultdict(list)

    for u, v in edges:
        adj[u].append(v)
        in_degree[v] += 1

    queue = deque([i for i in range(n) if in_degree[i] == 0])
    order = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return order if len(order) == n else []   # empty if cycle detected


# Test
edges = [(0, 1), (0, 2), (1, 3), (2, 3)]
print("Topo DFS:", topological_sort_dfs(4, edges))    # [0, 2, 1, 3] or similar
print("Topo Kahn:", topological_sort_kahn(4, edges))  # [0, 1, 2, 3] or similar


# ─────────────────────────────────────────────────────────────────────────────
# 8. UNION-FIND (DSU) — Path Compression + Union by Rank
# ─────────────────────────────────────────────────────────────────────────────
# Find: O(α(n)) amortized (nearly O(1))
# Union: O(α(n)) amortized

class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))   # each node is its own parent initially
        self.rank = [0] * n            # rank = approximate depth of tree
        self.components = n            # number of connected components

    def find(self, x):
        """Find root with path compression."""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])   # path compression
        return self.parent[x]

    def union(self, x, y):
        """Union by rank — attach smaller tree under larger tree."""
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return False   # already same component
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx           # ry becomes child of rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1
        self.components -= 1
        return True

    def connected(self, x, y):
        return self.find(x) == self.find(y)


# LeetCode 323 — Number of Connected Components in Undirected Graph
# Time: O(n + E * α(n))   Space: O(n)

def countComponents(n, edges):
    """Count connected components using Union-Find."""
    uf = UnionFind(n)
    for u, v in edges:
        uf.union(u, v)
    return uf.components


# Test
print("Components:", countComponents(5, [[0,1],[1,2],[3,4]]))   # 2
print("Components:", countComponents(5, [[0,1],[1,2],[2,3],[3,4]]))  # 1


# ─────────────────────────────────────────────────────────────────────────────
# 9. DIJKSTRA'S ALGORITHM — Shortest Path (Single Source)
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 743 — Network Delay Time
# Time: O((V + E) log V)   Space: O(V + E)
# Requires non-negative edge weights.

def dijkstra(n, edges, src):
    """
    Find shortest distances from src to all other nodes.
    Uses min-heap (priority queue).

    State: dist[node] = shortest distance from src to node
    Relaxation: if dist[u] + w < dist[v], update dist[v]
    """
    # Build adjacency list: graph[u] = [(weight, v), ...]
    graph = defaultdict(list)
    for u, v, w in edges:
        graph[u].append((w, v))
        graph[v].append((w, u))

    dist = {i: float('inf') for i in range(1, n + 1)}
    dist[src] = 0

    # Min-heap: (distance, node)
    heap = [(0, src)]

    while heap:
        d, node = heapq.heappop(heap)

        # Skip if we already found a shorter path
        if d > dist[node]:
            continue

        for weight, neighbor in graph[node]:
            new_dist = dist[node] + weight
            if new_dist < dist[neighbor]:
                dist[neighbor] = new_dist
                heapq.heappush(heap, (new_dist, neighbor))

    return dist


# LeetCode 743 — Network Delay Time
def networkDelayTime(times, n, k):
    """
    Find time for signal to reach ALL nodes from node k.
    Returns -1 if not all nodes reachable.
    times = [u, v, w]: signal from u to v takes w time.
    """
    graph = defaultdict(list)
    for u, v, w in times:
        graph[u].append((w, v))

    dist = {i: float('inf') for i in range(1, n + 1)}
    dist[k] = 0
    heap = [(0, k)]

    while heap:
        d, node = heapq.heappop(heap)
        if d > dist[node]:
            continue
        for weight, neighbor in graph[node]:
            new_dist = dist[node] + weight
            if new_dist < dist[neighbor]:
                dist[neighbor] = new_dist
                heapq.heappush(heap, (new_dist, neighbor))

    max_dist = max(dist.values())
    return max_dist if max_dist < float('inf') else -1


# Test
times = [[2,1,1],[2,3,1],[3,4,1]]
print("Network Delay:", networkDelayTime(times, 4, 2))   # 2


# ─────────────────────────────────────────────────────────────────────────────
# 10. WORD LADDER (BFS)
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 127
# Time: O(M^2 * N) where M = word length, N = number of words
# Space: O(M^2 * N)

def ladderLength(beginWord, endWord, wordList):
    """
    Find shortest transformation sequence from beginWord to endWord.
    Each step: change exactly one letter, result must be in wordList.
    Returns length of shortest sequence (0 if impossible).

    BFS strategy:
    - Build pattern map: 'hot' -> {'*ot': [hot, dot], 'h*t': [hot], 'ho*': [hot]}
    - BFS from beginWord, each level = one transformation step
    """
    word_set = set(wordList)
    if endWord not in word_set:
        return 0

    # Build pattern -> [words] mapping
    pattern_map = defaultdict(list)
    all_words = [beginWord] + list(wordList)
    for word in all_words:
        for i in range(len(word)):
            pattern = word[:i] + '*' + word[i+1:]
            pattern_map[pattern].append(word)

    visited = set([beginWord])
    queue = deque([(beginWord, 1)])   # (word, steps)

    while queue:
        word, steps = queue.popleft()
        for i in range(len(word)):
            pattern = word[:i] + '*' + word[i+1:]
            for neighbor in pattern_map[pattern]:
                if neighbor == endWord:
                    return steps + 1
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, steps + 1))

    return 0


# Test
print("Word Ladder:", ladderLength("hit", "cog", ["hot","dot","dog","lot","log","cog"]))  # 5
print("Word Ladder:", ladderLength("hit", "cog", ["hot","dot","dog","lot","log"]))         # 0


# ─────────────────────────────────────────────────────────────────────────────
# COMPLEXITY SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
"""
Algorithm                   Time Complexity     Space Complexity
─────────────────────────────────────────────────────────────────
BFS / DFS                   O(V + E)            O(V)
Number of Islands           O(m * n)            O(m * n)
Clone Graph                 O(V + E)            O(V)
Course Schedule (Kahn's)    O(V + E)            O(V + E)
Topological Sort (DFS)      O(V + E)            O(V + E)
Topological Sort (Kahn's)   O(V + E)            O(V + E)
Union-Find (path+rank)      O(α(n)) per op      O(n)
Connected Components        O(n + E * α(n))     O(n)
Dijkstra's (heap)           O((V+E) log V)      O(V + E)
Word Ladder                 O(M^2 * N)          O(M^2 * N)
─────────────────────────────────────────────────────────────────
V = vertices, E = edges, M = word length, N = word count
α = inverse Ackermann function (effectively constant)
"""
