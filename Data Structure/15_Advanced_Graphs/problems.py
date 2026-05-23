"""
╔══════════════════════════════════════════════════════════════════╗
║             ADVANCED GRAPHS — 10 LeetCode-Style Problems         ║
╚══════════════════════════════════════════════════════════════════╝
"""

from typing import List, Optional, Dict
from collections import defaultdict, deque
import heapq

# ── Shared Union-Find class ───────────────────
class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n
        self.components = n

    def find(self, x: int) -> int:
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: int, y: int) -> bool:
        rx, ry = self.find(x), self.find(y)
        if rx == ry: return False
        if self.rank[rx] < self.rank[ry]: rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]: self.rank[rx] += 1
        self.components -= 1
        return True

# ══════════════════════════════════════════════════════════════════
# Problem 1: Network Delay Time — Dijkstra (LC 743)
# ══════════════════════════════════════════════════════════════════
def networkDelayTime(times: List[List[int]], n: int, k: int) -> int:
    """
    Nodes 1..n. Send signal from k. times[i]=[u,v,w] = edge weight.
    Return time for ALL nodes to receive the signal, or -1 if impossible.
    = Maximum shortest path from k to all nodes.

    Approach: Dijkstra from k. Answer = max(dist values).

    Example:
      times=[[2,1,1],[2,3,1],[3,4,1]], n=4, k=2 → 2
    """
    graph = defaultdict(list)
    for u, v, w in times:
        graph[u].append((v, w))

    dist = {i: float('inf') for i in range(1, n+1)}
    dist[k] = 0
    heap = [(0, k)]

    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]: continue
        for v, w in graph[u]:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                heapq.heappush(heap, (dist[v], v))

    max_dist = max(dist.values())
    return max_dist if max_dist != float('inf') else -1

print("=== Network Delay Time ===")
print(networkDelayTime([[2,1,1],[2,3,1],[3,4,1]], 4, 2))  # 2
print(networkDelayTime([[1,2,1]], 2, 1))                   # 1
# Time: O((V+E) log V) | Space: O(V+E)

# ══════════════════════════════════════════════════════════════════
# Problem 2: Cheapest Flights Within K Stops — Bellman-Ford (LC 787)
# ══════════════════════════════════════════════════════════════════
def findCheapestPrice(n: int, flights: List[List[int]], src: int, dst: int, k: int) -> int:
    """
    Find cheapest price from src to dst with at most k stops.
    (k stops = k+1 edges in the path)

    Approach: Bellman-Ford with k+1 relaxation rounds.
    Use a copy each round to avoid using edges from the same round.

    Example:
      n=4, flights=[[0,1,100],[1,2,100],[2,0,100],[1,3,600],[2,3,200]]
      src=0, dst=3, k=1 → 700
    """
    dist = [float('inf')] * n
    dist[src] = 0

    for _ in range(k + 1):  # at most k+1 edges
        temp = dist[:]
        for u, v, w in flights:
            if dist[u] != float('inf') and dist[u] + w < temp[v]:
                temp[v] = dist[u] + w
        dist = temp

    return dist[dst] if dist[dst] != float('inf') else -1

print("\n=== Cheapest Flights Within K Stops ===")
print(findCheapestPrice(4,[[0,1,100],[1,2,100],[2,0,100],[1,3,600],[2,3,200]],0,3,1))  # 700
print(findCheapestPrice(3,[[0,1,100],[1,2,100],[0,2,500]],0,2,1))  # 200
# Time: O(k * E) | Space: O(V)

# ══════════════════════════════════════════════════════════════════
# Problem 3: Find the City With Smallest Reachable — Floyd-Warshall (LC 1334)
# ══════════════════════════════════════════════════════════════════
def findTheCity(n: int, edges: List[List[int]], distanceThreshold: int) -> int:
    """
    Find the city with the fewest number of cities reachable within distanceThreshold.
    If tie, return the city with largest index.

    Approach: Floyd-Warshall for all-pairs shortest path.

    Example:
      n=4, edges=[[0,1,3],[1,2,1],[1,3,4],[2,3,1]], distanceThreshold=4 → 3
    """
    INF = float('inf')
    dist = [[INF] * n for _ in range(n)]
    for i in range(n): dist[i][i] = 0
    for u, v, w in edges:
        dist[u][v] = dist[v][u] = w

    for k in range(n):
        for i in range(n):
            for j in range(n):
                dist[i][j] = min(dist[i][j], dist[i][k] + dist[k][j])

    result = -1
    min_count = n
    for i in range(n):
        count = sum(1 for j in range(n) if i != j and dist[i][j] <= distanceThreshold)
        if count <= min_count:
            min_count = count
            result = i

    return result

print("\n=== Find the City (Floyd-Warshall) ===")
print(findTheCity(4,[[0,1,3],[1,2,1],[1,3,4],[2,3,1]],4))  # 3
print(findTheCity(5,[[0,1,2],[0,4,8],[1,2,3],[1,4,2],[2,3,1],[3,4,1]],2)) # 0
# Time: O(V³) | Space: O(V²)

# ══════════════════════════════════════════════════════════════════
# Problem 4: Number of Islands II — Union Find (LC 305)
# ══════════════════════════════════════════════════════════════════
def numIslands2(m: int, n: int, positions: List[List[int]]) -> List[int]:
    """
    Initially empty m×n grid. Add land cells one by one.
    After each addition, return number of islands.

    Approach: Union-Find. Each cell has id = r*n + c.
    On adding cell, try to union with adjacent land cells.

    Example:
      m=3, n=3, positions=[[0,0],[0,1],[1,2],[2,1]] → [1,1,2,3]
    """
    uf = UnionFind(m * n)
    land = set()
    result = []
    islands = 0

    for r, c in positions:
        if (r, c) in land:
            result.append(islands)
            continue
        land.add((r, c))
        islands += 1
        cell_id = r * n + c

        for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
            nr, nc = r+dr, c+dc
            if 0<=nr<m and 0<=nc<n and (nr, nc) in land:
                if uf.union(cell_id, nr*n+nc):
                    islands -= 1  # merged two islands

        result.append(islands)

    return result

print("\n=== Number of Islands II ===")
print(numIslands2(3,3,[[0,0],[0,1],[1,2],[2,1]]))  # [1,1,2,3]
# Time: O(k * α(m*n)) | Space: O(m*n)

# ══════════════════════════════════════════════════════════════════
# Problem 5: Redundant Connection — Union Find (LC 684)
# ══════════════════════════════════════════════════════════════════
def findRedundantConnection(edges: List[List[int]]) -> List[int]:
    """
    Find the edge that can be removed to make the graph a tree.
    If multiple answers, return the one that appears last.

    Approach: Union-Find. Add edges one by one. When adding edge (u,v)
    would create a cycle (u and v already connected), that's the answer.

    Example:
      [[1,2],[1,3],[2,3]] → [2,3]
      [[1,2],[2,3],[3,4],[1,4],[1,5]] → [1,4]
    """
    n = len(edges)
    uf = UnionFind(n + 1)  # nodes 1..n

    for u, v in edges:
        if not uf.union(u, v):
            return [u, v]  # this edge creates a cycle
    return []

print("\n=== Redundant Connection ===")
print(findRedundantConnection([[1,2],[1,3],[2,3]]))          # [2,3]
print(findRedundantConnection([[1,2],[2,3],[3,4],[1,4],[1,5]]))  # [1,4]
# Time: O(n * α(n)) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 6: Accounts Merge — Union Find (LC 721)
# ══════════════════════════════════════════════════════════════════
def accountsMerge(accounts: List[List[str]]) -> List[List[str]]:
    """
    Merge accounts that share email addresses.
    First element is name, rest are emails.

    Approach: Union-Find on emails. Each email maps to an index.
    Emails in the same account get unioned. Then group by root.

    Example:
      [["John","j@j","x@x"],["John","j@j","y@y"],["Mary","m@m"]]
      → [["John","j@j","x@x","y@y"],["Mary","m@m"]]
    """
    email_to_idx = {}
    email_to_name = {}
    idx = 0

    for account in accounts:
        name = account[0]
        for email in account[1:]:
            if email not in email_to_idx:
                email_to_idx[email] = idx
                idx += 1
            email_to_name[email] = name

    uf = UnionFind(idx)
    for account in accounts:
        first_idx = email_to_idx[account[1]]
        for email in account[2:]:
            uf.union(first_idx, email_to_idx[email])

    # Group emails by root
    groups = defaultdict(list)
    for email, i in email_to_idx.items():
        root = uf.find(i)
        groups[root].append(email)

    result = []
    for root, emails in groups.items():
        emails.sort()
        # Find name from first email in any original account with this root
        name = email_to_name[emails[0]]
        result.append([name] + emails)

    return result

print("\n=== Accounts Merge ===")
accounts = [["John","j@j.com","x@x.com"],["John","j@j.com","y@y.com"],["Mary","m@m.com"]]
for acc in sorted(accountsMerge(accounts)):
    print(" ", acc)
# Time: O(n * m * α(n*m)) | Space: O(n*m)

# ══════════════════════════════════════════════════════════════════
# Problem 7: Min Cost to Connect All Points — Kruskal MST (LC 1584)
# ══════════════════════════════════════════════════════════════════
def minCostConnectPoints(points: List[List[int]]) -> int:
    """
    Connect all points with minimum cost. Cost = Manhattan distance.
    = Minimum Spanning Tree.

    Approach: Kruskal's — sort all edges by weight, add if no cycle.
    Optimization: Prim's is better here (avoid generating all O(n²) edges upfront).

    Example:
      [[0,0],[2,2],[3,10],[5,2],[7,0]] → 20
    """
    n = len(points)
    # Generate all edges (Prim's approach to avoid O(n²) edge generation)
    uf = UnionFind(n)
    # Use Prim's with heap for efficiency
    visited = set()
    heap = [(0, 0)]  # (cost, point_index)
    total = 0

    while heap and len(visited) < n:
        cost, u = heapq.heappop(heap)
        if u in visited: continue
        visited.add(u)
        total += cost
        for v in range(n):
            if v not in visited:
                dist = abs(points[u][0]-points[v][0]) + abs(points[u][1]-points[v][1])
                heapq.heappush(heap, (dist, v))

    return total

print("\n=== Min Cost to Connect All Points ===")
print(minCostConnectPoints([[0,0],[2,2],[3,10],[5,2],[7,0]]))  # 20
print(minCostConnectPoints([[3,12],[-2,5],[-4,1]]))            # 18
# Time: O(n² log n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 8: Swim in Rising Water — Dijkstra (LC 778)
# ══════════════════════════════════════════════════════════════════
def swimInWater(grid: List[List[int]]) -> int:
    """
    At time t, can swim through cells with value <= t.
    Find minimum t to swim from (0,0) to (n-1,n-1).
    = Find path minimizing the maximum cell value.

    Approach: Dijkstra where "distance" = max value on path to a cell.

    Example:
      [[0,2],[1,3]] → 3
    """
    n = len(grid)
    dist = [[float('inf')] * n for _ in range(n)]
    dist[0][0] = grid[0][0]
    heap = [(grid[0][0], 0, 0)]

    while heap:
        d, r, c = heapq.heappop(heap)
        if d > dist[r][c]: continue
        if r == n-1 and c == n-1: return d
        for dr, dc in [(0,1),(0,-1),(1,0),(-1,0)]:
            nr, nc = r+dr, c+dc
            if 0<=nr<n and 0<=nc<n:
                new_d = max(d, grid[nr][nc])
                if new_d < dist[nr][nc]:
                    dist[nr][nc] = new_d
                    heapq.heappush(heap, (new_d, nr, nc))

    return dist[n-1][n-1]

print("\n=== Swim in Rising Water ===")
print(swimInWater([[0,2],[1,3]]))       # 3
print(swimInWater([[0,1,2,3,4],[24,23,22,21,5],[12,13,14,15,16],[11,17,18,19,20],[10,9,8,7,6]]))  # 16
# Time: O(n² log n) | Space: O(n²)

# ══════════════════════════════════════════════════════════════════
# Problem 9: Reconstruct Itinerary — Eulerian Path (LC 332)
# ══════════════════════════════════════════════════════════════════
def findItinerary(tickets: List[List[str]]) -> List[str]:
    """
    Reconstruct itinerary using all tickets exactly once. Start from "JFK".
    Use smallest lexical order when multiple choices exist.

    Approach: Hierholzer's algorithm for Eulerian path.
    Sort destinations (so we explore lex-smallest first).
    DFS — when a node has no more neighbors, prepend to result.

    Example:
      [["MUC","LHR"],["JFK","MUC"],["SFO","SJC"],["LHR","SFO"]] → ["JFK","MUC","LHR","SFO","SJC"]
    """
    graph = defaultdict(list)
    for src, dst in sorted(tickets, reverse=True):
        graph[src].append(dst)

    result = []
    def dfs(node):
        while graph[node]:
            dfs(graph[node].pop())
        result.append(node)

    dfs("JFK")
    return result[::-1]

print("\n=== Reconstruct Itinerary ===")
print(findItinerary([["MUC","LHR"],["JFK","MUC"],["SFO","SJC"],["LHR","SFO"]]))
# ["JFK","MUC","LHR","SFO","SJC"]
print(findItinerary([["JFK","SFO"],["JFK","ATL"],["SFO","ATL"],["ATL","JFK"],["ATL","SFO"]]))
# ["JFK","ATL","JFK","SFO","ATL","SFO"]
# Time: O(E log E) | Space: O(E)

# ══════════════════════════════════════════════════════════════════
# Problem 10: Critical Connections — Bridges (LC 1192)
# ══════════════════════════════════════════════════════════════════
def criticalConnections(n: int, connections: List[List[int]]) -> List[List[int]]:
    """
    Find all critical connections (bridges) — edges whose removal disconnects the graph.

    Approach: Tarjan's Bridge Finding Algorithm.
    DFS with discovery time (disc) and low-link value (low).
    low[v] = min discovery time reachable from v's subtree.
    Edge (u,v) is a bridge if low[v] > disc[u].

    Example:
      n=4, connections=[[0,1],[1,2],[2,0],[1,3]] → [[1,3]]
    """
    graph = defaultdict(list)
    for u, v in connections:
        graph[u].append(v)
        graph[v].append(u)

    disc = [-1] * n
    low = [0] * n
    result = []
    timer = [0]

    def dfs(u, parent):
        disc[u] = low[u] = timer[0]
        timer[0] += 1
        for v in graph[u]:
            if v == parent: continue
            if disc[v] == -1:
                dfs(v, u)
                low[u] = min(low[u], low[v])
                if low[v] > disc[u]:
                    result.append([u, v])  # bridge!
            else:
                low[u] = min(low[u], disc[v])

    for i in range(n):
        if disc[i] == -1:
            dfs(i, -1)

    return result

print("\n=== Critical Connections (Bridges) ===")
print(criticalConnections(4, [[0,1],[1,2],[2,0],[1,3]]))  # [[1,3]]
print(criticalConnections(2, [[0,1]]))                    # [[0,1]]
# Time: O(V+E) | Space: O(V+E)

print("\n✓ All 10 Advanced Graph problems solved!")
