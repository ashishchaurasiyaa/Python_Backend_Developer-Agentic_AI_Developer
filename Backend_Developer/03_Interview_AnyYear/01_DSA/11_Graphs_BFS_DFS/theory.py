"""
╔══════════════════════════════════════════════════════════════════╗
║              GRAPHS BFS & DFS — Complete Theory Guide            ║
╚══════════════════════════════════════════════════════════════════╝

WHAT IS A GRAPH?
─────────────────
A graph G = (V, E) consists of:
  V = set of vertices (nodes)
  E = set of edges (connections between nodes)

Types:
  Directed: edges have direction (A→B doesn't mean B→A)
  Undirected: edges are bidirectional
  Weighted: edges have a cost/weight
  Cyclic / Acyclic (DAG = Directed Acyclic Graph)

GRAPH REPRESENTATIONS
──────────────────────
1. Adjacency List: dict mapping node → list of neighbors
   Space: O(V + E), best for sparse graphs
2. Adjacency Matrix: 2D array [V][V]
   Space: O(V²), best for dense graphs or quick edge lookup

COMPLEXITY TABLE
─────────────────────────────────────────────────────────────────
Algorithm           Time            Space       Notes
─────────────────────────────────────────────────────────────────
BFS                 O(V + E)        O(V)        Shortest path (unweighted)
DFS                 O(V + E)        O(V)        Cycle detect, topo sort
Topological Sort    O(V + E)        O(V)        DAGs only
Connected Comps     O(V + E)        O(V)        BFS/DFS
─────────────────────────────────────────────────────────────────
"""

from typing import List, Dict, Set
from collections import deque, defaultdict

# ─────────────────────────────────────────────
# 1. GRAPH REPRESENTATIONS
# ─────────────────────────────────────────────
print("=" * 60)
print("1. GRAPH REPRESENTATIONS")
print("=" * 60)

# Adjacency list (undirected)
graph_adj_list = {
    0: [1, 2],
    1: [0, 3],
    2: [0, 3, 4],
    3: [1, 2],
    4: [2]
}

# Adjacency matrix (same graph)
graph_adj_matrix = [
    [0, 1, 1, 0, 0],
    [1, 0, 0, 1, 0],
    [1, 0, 0, 1, 1],
    [0, 1, 1, 0, 0],
    [0, 0, 1, 0, 0]
]

print("Adjacency List:", graph_adj_list)
print("Adjacency Matrix:")
for row in graph_adj_matrix:
    print(" ", row)

# ─────────────────────────────────────────────
# 2. BFS — Breadth-First Search
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("2. BFS — Breadth-First Search")
print("=" * 60)

"""
BFS explores all neighbors at depth d before depth d+1.
Uses a QUEUE.

Properties:
  ✓ Finds SHORTEST PATH in unweighted graph
  ✓ Visits nodes level by level
  ✓ Complete: will find a solution if one exists
  ✗ Uses more memory than DFS (stores all nodes at current frontier)

Template:
  visited = set([start])
  queue = deque([start])
  while queue:
      node = queue.popleft()
      # process node
      for neighbor in graph[node]:
          if neighbor not in visited:
              visited.add(neighbor)
              queue.append(neighbor)
"""

def bfs(graph: Dict, start: int) -> List[int]:
    """BFS traversal. Returns nodes in BFS order."""
    visited = set([start])
    queue = deque([start])
    order = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return order

print(f"BFS from 0: {bfs(graph_adj_list, 0)}")  # [0,1,2,3,4]

def bfs_shortest_path(graph: Dict, start: int, end: int) -> int:
    """Find shortest path length between start and end."""
    if start == end:
        return 0
    visited = set([start])
    queue = deque([(start, 0)])
    while queue:
        node, dist = queue.popleft()
        for neighbor in graph.get(node, []):
            if neighbor == end:
                return dist + 1
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, dist + 1))
    return -1  # not reachable

print(f"Shortest path 0→4: {bfs_shortest_path(graph_adj_list, 0, 4)}")  # 2

# ─────────────────────────────────────────────
# 3. DFS — Depth-First Search
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("3. DFS — Depth-First Search")
print("=" * 60)

"""
DFS explores as far as possible before backtracking.
Uses a STACK (or recursion).

Properties:
  ✓ Lower memory than BFS (only stores current path)
  ✓ Good for: cycle detection, topological sort, connected components,
              tree problems, backtracking
  ✗ Does NOT find shortest path (can go deep and miss shorter paths)

Recursive Template:
  visited = set()
  def dfs(node):
      if node in visited: return
      visited.add(node)
      # process node
      for neighbor in graph[node]:
          dfs(neighbor)

Iterative Template:
  visited = set()
  stack = [start]
  while stack:
      node = stack.pop()
      if node in visited: continue
      visited.add(node)
      for neighbor in graph[node]:
          stack.append(neighbor)
"""

def dfs_recursive(graph: Dict, start: int, visited: Set = None) -> List[int]:
    """Recursive DFS traversal."""
    if visited is None:
        visited = set()
    visited.add(start)
    order = [start]
    for neighbor in graph.get(start, []):
        if neighbor not in visited:
            order.extend(dfs_recursive(graph, neighbor, visited))
    return order

def dfs_iterative(graph: Dict, start: int) -> List[int]:
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
        for neighbor in graph.get(node, []):
            stack.append(neighbor)
    return order

print(f"DFS recursive from 0: {dfs_recursive(graph_adj_list, 0)}")
print(f"DFS iterative from 0: {dfs_iterative(graph_adj_list, 0)}")

# ─────────────────────────────────────────────
# 4. CYCLE DETECTION
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("4. CYCLE DETECTION")
print("=" * 60)

"""
UNDIRECTED GRAPH: DFS — cycle exists if we visit an already-visited node
that is NOT the direct parent.

DIRECTED GRAPH: DFS — cycle exists if we encounter a node that's in the
CURRENT PATH (recursion stack). Use two sets: visited and in_stack.
"""

def has_cycle_directed(graph: Dict, num_nodes: int) -> bool:
    """Detect cycle in directed graph using DFS with recursion stack."""
    visited = set()
    in_stack = set()

    def dfs(node):
        visited.add(node)
        in_stack.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor): return True
            elif neighbor in in_stack:
                return True  # back edge = cycle!
        in_stack.remove(node)
        return False

    for node in range(num_nodes):
        if node not in visited:
            if dfs(node): return True
    return False

# 0→1→2→0 (cycle)
cyclic_graph = {0: [1], 1: [2], 2: [0]}
print(f"Cyclic graph has cycle: {has_cycle_directed(cyclic_graph, 3)}")   # True
# 0→1, 0→2, 1→3 (no cycle)
acyclic_graph = {0: [1, 2], 1: [3], 2: [], 3: []}
print(f"Acyclic graph has cycle: {has_cycle_directed(acyclic_graph, 4)}") # False

# ─────────────────────────────────────────────
# 5. TOPOLOGICAL SORT
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("5. TOPOLOGICAL SORT — Two Approaches")
print("=" * 60)

"""
Topological Sort: linear ordering of vertices in a DAG such that
for every directed edge u→v, u comes before v.
ONLY works on DAGs (no cycles).

Applications: Course scheduling, build systems, task dependencies.
"""

# Method 1: Kahn's Algorithm (BFS-based)
def topo_sort_kahn(graph: Dict, num_nodes: int) -> List[int]:
    """
    Kahn's BFS topological sort.
    1. Compute in-degree of all nodes.
    2. Add all zero in-degree nodes to queue.
    3. Process: dequeue, add to result, reduce neighbors' in-degree.
    4. If neighbor's in-degree becomes 0, add to queue.
    If result length < num_nodes → cycle exists!
    """
    in_degree = [0] * num_nodes
    for node in graph:
        for neighbor in graph[node]:
            in_degree[neighbor] += 1

    queue = deque([i for i in range(num_nodes) if in_degree[i] == 0])
    result = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in graph.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return result if len(result) == num_nodes else []  # [] = cycle

# Method 2: DFS-based
def topo_sort_dfs(graph: Dict, num_nodes: int) -> List[int]:
    """DFS-based topo sort. Append to result AFTER visiting all neighbors (post-order). Reverse."""
    visited = set()
    result = []

    def dfs(node):
        visited.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor)
        result.append(node)  # post-order

    for i in range(num_nodes):
        if i not in visited:
            dfs(i)

    return result[::-1]  # reverse for topological order

dag = {0: [1, 2], 1: [3], 2: [3], 3: []}
print(f"Topo sort (Kahn): {topo_sort_kahn(dag, 4)}")   # [0,1,2,3] or [0,2,1,3]
print(f"Topo sort (DFS):  {topo_sort_dfs(dag, 4)}")    # [0,1,2,3] or similar

# ─────────────────────────────────────────────
# 6. CONNECTED COMPONENTS
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("6. CONNECTED COMPONENTS")
print("=" * 60)

def count_components(n: int, edges: List[List[int]]) -> int:
    """Count connected components using BFS/DFS."""
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

print(f"Components in n=5, edges=[[0,1],[1,2],[3,4]]: {count_components(5, [[0,1],[1,2],[3,4]])}")  # 2

# ─────────────────────────────────────────────
# 7. MULTI-SOURCE BFS (Grid Problems)
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("7. MULTI-SOURCE BFS — Grid Traversal")
print("=" * 60)

"""
Multi-source BFS: start BFS from MULTIPLE sources simultaneously.
Used for: "distance from nearest X", "paint fill", rotten oranges.

Key: initialize queue with ALL sources at distance 0.
"""

def walls_and_gates_demo(rooms: List[List[int]]) -> None:
    """Fill each empty room with distance to nearest gate."""
    INF = float('inf')
    rows, cols = len(rooms), len(rooms[0])
    queue = deque()

    # Initialize: all gates (0) are sources
    for r in range(rows):
        for c in range(cols):
            if rooms[r][c] == 0:
                queue.append((r, c, 0))

    while queue:
        r, c, dist = queue.popleft()
        for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and rooms[nr][nc] == INF:
                rooms[nr][nc] = dist + 1
                queue.append((nr, nc, dist + 1))

# ─────────────────────────────────────────────
# 8. INTERVIEW Q&A
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("INTERVIEW Q&A")
print("=" * 60)

qa = """
Q1: When do you use BFS vs DFS?
A1: BFS: shortest path in unweighted graph, level-order operations.
    DFS: cycle detection, topological sort, connected components,
         tree path problems, backtracking, maze solving.
    Rule of thumb: If "shortest" or "minimum distance" → BFS.
    Otherwise, DFS is often simpler to implement.

Q2: How do you detect a cycle in an undirected graph?
A2: DFS: If we visit a node that's already visited AND it's not the
    direct parent of the current node → cycle exists.
    Alternatively: Union-Find — if adding edge (u,v) and they're already
    in the same component → cycle.

Q3: How do you detect a cycle in a directed graph?
A3: DFS with a "recursion stack" set. If we encounter a node in the
    current DFS path (in_stack) → cycle exists (back edge).
    Kahn's algorithm: if topological sort doesn't include all nodes → cycle.

Q4: What is the difference between connected and strongly connected?
A4: Connected (undirected): there's a path between every pair of nodes.
    Strongly connected (directed): for every pair (u,v), there's a directed
    path from u→v AND from v→u.

Q5: What is topological sort and when does it work?
A5: Linear ordering of DAG vertices where u comes before v for edge u→v.
    Only works on DAGs (no cycles). Used for: dependency resolution,
    course scheduling, build systems.

Q6: How do you find the number of islands?
A6: DFS/BFS on a grid. For each unvisited '1', do a DFS marking all
    connected '1's as visited. Count the number of such DFS calls.

Q7: Can you do BFS on a grid directly?
A7: Yes. Treat each cell (r,c) as a node. Neighbors are the 4 adjacent cells.
    Use a visited set or modify the grid (mark as visited) to avoid revisiting.

Q8: What is the complexity of DFS on a graph with V vertices and E edges?
A8: O(V + E) — each vertex is visited once (O(V)), each edge is explored once (O(E)).
"""
print(qa)
