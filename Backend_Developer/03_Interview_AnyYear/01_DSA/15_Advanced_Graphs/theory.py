"""
╔══════════════════════════════════════════════════════════════════╗
║             ADVANCED GRAPHS — Complete Theory Guide              ║
╚══════════════════════════════════════════════════════════════════╝

TOPICS COVERED:
  1. Dijkstra's Algorithm (Single-Source Shortest Path, non-negative weights)
  2. Bellman-Ford Algorithm (SSSP, handles negative weights/cycles)
  3. Floyd-Warshall (All-Pairs Shortest Path)
  4. Union-Find (Disjoint Set Union) with Path Compression + Union by Rank
  5. Topological Sort (Kahn's BFS + DFS)
  6. Minimum Spanning Tree (Kruskal + Prim)

COMPLEXITY TABLE
─────────────────────────────────────────────────────────────────
Algorithm           Time               Space     Notes
─────────────────────────────────────────────────────────────────
Dijkstra (heap)     O((V+E) log V)     O(V+E)    Non-negative weights
Bellman-Ford        O(V*E)             O(V)      Handles neg weights/cycles
Floyd-Warshall      O(V³)              O(V²)     All-pairs
Union-Find          O(α(n)) per op     O(n)      Inverse Ackermann ≈ O(1)
Topo Sort (Kahn)    O(V+E)             O(V+E)    DAGs only
Kruskal MST         O(E log E)         O(V+E)    Sort edges + Union-Find
Prim MST            O((V+E) log V)     O(V+E)    Heap-based
─────────────────────────────────────────────────────────────────
"""

import heapq
from typing import List, Dict, Tuple
from collections import defaultdict, deque

# ─────────────────────────────────────────────
# 1. DIJKSTRA'S ALGORITHM
# ─────────────────────────────────────────────
print("=" * 60)
print("1. DIJKSTRA'S ALGORITHM")
print("=" * 60)

"""
PROBLEM: Shortest path from source to all other nodes (non-negative weights).

IDEA: Greedy BFS with a min-heap. At each step, process the node with
the smallest tentative distance. Update neighbors if shorter path found.

WHY IT WORKS: Once a node is popped from the heap, its shortest distance
is finalized (can't be improved further, since all weights >= 0).

FAILS FOR: Negative weights. Use Bellman-Ford instead.

TEMPLATE:
  dist = {node: inf for all nodes}
  dist[source] = 0
  heap = [(0, source)]
  while heap:
      d, u = heappop(heap)
      if d > dist[u]: continue  # stale entry
      for v, w in graph[u]:
          if dist[u] + w < dist[v]:
              dist[v] = dist[u] + w
              heappush(heap, (dist[v], v))
"""

def dijkstra(graph: Dict, source: int, n: int) -> List[int]:
    """
    Returns shortest distances from source to all nodes.
    graph: {node: [(neighbor, weight), ...]}
    """
    dist = [float('inf')] * n
    dist[source] = 0
    heap = [(0, source)]  # (distance, node)

    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue  # skip stale entry
        for v, w in graph.get(u, []):
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                heapq.heappush(heap, (dist[v], v))

    return dist

# Example
graph_d = {
    0: [(1, 4), (2, 1)],
    1: [(3, 1)],
    2: [(1, 2), (3, 5)],
    3: []
}
dist = dijkstra(graph_d, 0, 4)
print(f"Shortest distances from 0: {dist}")  # [0, 3, 1, 4]

# ─────────────────────────────────────────────
# 2. BELLMAN-FORD ALGORITHM
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("2. BELLMAN-FORD ALGORITHM")
print("=" * 60)

"""
PROBLEM: Shortest path from source, allows NEGATIVE weights.
Also DETECTS negative cycles.

IDEA: Relax ALL edges V-1 times. A shortest path has at most V-1 edges.
After V-1 rounds, if we can still relax an edge → negative cycle.

KEY INSIGHT:
  After k relaxation rounds, dist[v] = shortest path using at most k edges.
  After V-1 rounds, all shortest paths are found (if no neg cycles).

Variant for K stops (LC 787): only relax k+1 times, use copy of dist each round.
"""

def bellman_ford(n: int, edges: List[Tuple], source: int) -> List[float]:
    """
    n = number of nodes (0 to n-1)
    edges = [(u, v, weight), ...]
    Returns shortest distances or detects negative cycle.
    """
    dist = [float('inf')] * n
    dist[source] = 0

    for _ in range(n - 1):  # relax n-1 times
        for u, v, w in edges:
            if dist[u] != float('inf') and dist[u] + w < dist[v]:
                dist[v] = dist[u] + w

    # Check for negative cycles
    for u, v, w in edges:
        if dist[u] != float('inf') and dist[u] + w < dist[v]:
            print("  Negative cycle detected!")
            return []

    return dist

edges = [(0,1,4),(0,2,1),(2,1,2),(1,3,1),(2,3,5)]
print(f"Bellman-Ford from 0: {bellman_ford(4, edges, 0)}")  # [0,3,1,4]

# K-stops variant (LC 787)
def bellman_ford_k_stops(n: int, flights: List[List[int]], src: int, dst: int, k: int) -> int:
    """Cheapest flight within k stops."""
    dist = [float('inf')] * n
    dist[src] = 0
    for _ in range(k + 1):  # at most k+1 edges
        temp = dist[:]
        for u, v, w in flights:
            if dist[u] != float('inf') and dist[u] + w < temp[v]:
                temp[v] = dist[u] + w
        dist = temp
    return dist[dst] if dist[dst] != float('inf') else -1

print(f"K-stops test: {bellman_ford_k_stops(4,[[0,1,100],[1,2,100],[2,0,100],[1,3,600],[2,3,200]],0,3,1)}")  # 700

# ─────────────────────────────────────────────
# 3. FLOYD-WARSHALL ALGORITHM
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("3. FLOYD-WARSHALL ALGORITHM")
print("=" * 60)

"""
PROBLEM: ALL-PAIRS shortest path.

IDEA: For each intermediate node k, check if going through k gives a shorter path.
  dist[i][j] = min(dist[i][j], dist[i][k] + dist[k][j])

THREE NESTED LOOPS: k (intermediate), i (source), j (destination).

WHEN TO USE: Small graphs (V <= 500), or when you need all-pairs distances.
"""

def floyd_warshall(n: int, edges: List[Tuple]) -> List[List[float]]:
    """
    Returns dist[i][j] = shortest path from i to j.
    edges = [(u, v, weight), ...]
    """
    INF = float('inf')
    dist = [[INF] * n for _ in range(n)]
    for i in range(n):
        dist[i][i] = 0
    for u, v, w in edges:
        dist[u][v] = min(dist[u][v], w)  # handle multiple edges

    for k in range(n):        # intermediate node
        for i in range(n):    # source
            for j in range(n):  # destination
                if dist[i][k] + dist[k][j] < dist[i][j]:
                    dist[i][j] = dist[i][k] + dist[k][j]

    return dist

edges_fw = [(0,1,3),(0,2,8),(0,4,4),(1,3,1),(1,4,7),(2,1,4),(3,0,2),(3,2,5),(4,3,6)]
fw_result = floyd_warshall(5, edges_fw)
print("Floyd-Warshall distance matrix:")
for row in fw_result:
    print(" ", [x if x != float('inf') else 'inf' for x in row])

# ─────────────────────────────────────────────
# 4. UNION-FIND (Disjoint Set Union)
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("4. UNION-FIND (DSU)")
print("=" * 60)

"""
PROBLEM: Track connected components. Efficiently answer:
  - Are u and v in the same component?
  - Merge two components.

TWO OPTIMIZATIONS:
  1. Path Compression: When finding root, make all nodes on path point to root.
  2. Union by Rank: Always attach smaller tree under larger tree.

With both: O(α(n)) per operation ≈ O(1) amortized (α = inverse Ackermann).

APPLICATIONS:
  Cycle detection in undirected graphs, MST (Kruskal), dynamic connectivity.
"""

class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n
        self.components = n

    def find(self, x: int) -> int:
        """Find root with PATH COMPRESSION."""
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])  # path compression
        return self.parent[x]

    def union(self, x: int, y: int) -> bool:
        """Union by RANK. Returns True if they were in different components."""
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return False  # already same component (would create cycle)
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1
        self.components -= 1
        return True

    def connected(self, x: int, y: int) -> bool:
        return self.find(x) == self.find(y)

# Demo
uf = UnionFind(6)
print(f"Initially: {uf.components} components")
uf.union(0, 1); uf.union(1, 2); uf.union(3, 4)
print(f"After unions 0-1, 1-2, 3-4: {uf.components} components")
print(f"0 and 2 connected: {uf.connected(0, 2)}")  # True
print(f"0 and 3 connected: {uf.connected(0, 3)}")  # False

# ─────────────────────────────────────────────
# 5. MINIMUM SPANNING TREE
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("5. MINIMUM SPANNING TREE")
print("=" * 60)

"""
MST: A spanning tree with minimum total edge weight.
Properties: V-1 edges, connects all vertices, no cycles.

KRUSKAL'S: Sort edges by weight. Add edge if it doesn't form a cycle (Union-Find).
  Time: O(E log E)
  Best for: Sparse graphs (E << V²)

PRIM'S: Start from any node. Greedily add cheapest edge crossing the cut.
  Time: O((V+E) log V) with min-heap
  Best for: Dense graphs

Both are greedy and provably correct by the cut property.
"""

def kruskal_mst(n: int, edges: List[Tuple]) -> int:
    """
    Kruskal's MST. Returns total weight of MST.
    edges = [(weight, u, v), ...]
    """
    edges.sort()  # sort by weight
    uf = UnionFind(n)
    total_weight = 0
    edge_count = 0

    for w, u, v in edges:
        if uf.union(u, v):
            total_weight += w
            edge_count += 1
            if edge_count == n - 1:
                break  # MST complete

    return total_weight if edge_count == n - 1 else -1  # -1 if not connected

def prim_mst(n: int, adj: Dict) -> int:
    """
    Prim's MST using min-heap.
    adj: {node: [(neighbor, weight), ...]}
    """
    visited = set()
    heap = [(0, 0)]  # (weight, node), start from node 0
    total = 0

    while heap and len(visited) < n:
        w, u = heapq.heappop(heap)
        if u in visited:
            continue
        visited.add(u)
        total += w
        for v, weight in adj.get(u, []):
            if v not in visited:
                heapq.heappush(heap, (weight, v))

    return total if len(visited) == n else -1

# Example: 4 nodes, weighted edges
kruskal_edges = [(1,0,1),(2,0,2),(3,1,2),(4,1,3),(5,2,3)]
print(f"Kruskal MST weight: {kruskal_mst(4, kruskal_edges)}")  # 6

prim_adj = {0:[(1,1),(2,2)], 1:[(0,1),(2,3),(3,4)], 2:[(0,2),(1,3),(3,5)], 3:[(1,4),(2,5)]}
print(f"Prim MST weight: {prim_mst(4, prim_adj)}")  # 7

# ─────────────────────────────────────────────
# 6. INTERVIEW Q&A
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("INTERVIEW Q&A")
print("=" * 60)

qa = """
Q1: When do you use Dijkstra vs Bellman-Ford?
A1: Dijkstra: Non-negative edge weights. O((V+E)log V). Most practical cases.
    Bellman-Ford: Negative edge weights or need to detect negative cycles.
    O(V*E) — much slower. Used in routing protocols (RIP, OSPF in some contexts).

Q2: Why can't Dijkstra handle negative edges?
A2: Dijkstra's correctness relies on the property that once a node is extracted
    from the heap, its distance is finalized. With negative edges, a longer path
    that goes through a negative edge could be shorter — but that node was already
    finalized. This invariant breaks.

Q3: What is path compression in Union-Find?
A3: When finding the root of a node, make all nodes on the path point directly
    to the root. Future find operations on those nodes become O(1).
    Without it: O(log n) find. With it: O(α(n)) ≈ O(1) amortized.

Q4: What's the difference between Kruskal's and Prim's?
A4: Kruskal: Add cheapest edge that doesn't form a cycle. Needs sorting (O(E log E)).
    Uses Union-Find. Best for sparse graphs.
    Prim: Grow the MST from one node, always adding cheapest edge crossing the frontier.
    Uses min-heap (O((V+E)log V)). Best for dense graphs.

Q5: Can Floyd-Warshall detect negative cycles?
A5: Yes. After running Floyd-Warshall, if dist[i][i] < 0 for any node i,
    there's a negative cycle (we found a path from i to i with negative total weight).

Q6: What is the time complexity of Union-Find with both optimizations?
A6: O(α(n)) per operation, where α is the inverse Ackermann function.
    α(n) < 5 for any practical n (even 2^65536). Effectively constant O(1).

Q7: How do you find bridges (critical connections) in a graph?
A7: Use DFS with low-link values (Tarjan's bridge finding algorithm).
    An edge (u,v) is a bridge if removing it disconnects the graph.
    bridge condition: low[v] > disc[u] (v can't reach u without using edge (u,v))

Q8: What is topological sort used for?
A8: Finding a linear ordering of tasks with dependencies.
    Build system order, course prerequisites, package installations.
    Only works on DAGs (Directed Acyclic Graphs).
"""
print(qa)
