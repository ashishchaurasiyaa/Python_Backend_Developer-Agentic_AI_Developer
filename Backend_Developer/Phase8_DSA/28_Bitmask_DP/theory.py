"""
============================================================
BITMASK DP (DP with Subset Bitmask)
============================================================

WHAT IS BITMASK DP?
-------------------
DP where state includes a BITMASK representing a subset.
Each bit corresponds to whether an element is in the subset.

Example: For N items, mask of bits = which items selected.
N=4, mask=0b1011 → items 0, 1, 3 selected (not 2).

WHEN TO USE?
------------
- N is SMALL (≤ 20-22 typically)
- Need to enumerate subsets or track "which items used"
- Problem has 2^N state explosion potential

CLASSIC PROBLEMS
----------------
1. Traveling Salesman Problem (TSP) — O(N^2 * 2^N)
2. Assignment Problem
3. Hamilton Path/Cycle counting
4. Set cover
5. Counting subsets with given property
6. Job scheduling with constraints

COMPLEXITY
----------
States = 2^N (one per subset)
Transitions = O(N) per state typically
Total = O(N * 2^N) — fits if N ≤ 20

COMMON BIT OPERATIONS
---------------------
mask & (1 << i)        : check if bit i is set
mask | (1 << i)        : set bit i
mask & ~(1 << i)       : clear bit i
mask ^ (1 << i)        : toggle bit i
bin(mask).count('1')   : popcount (number of set bits)
mask == (1 << N) - 1   : all N bits set

# Iterate over all SUBSETS of mask:
sub = mask
while sub > 0:
    # use sub
    sub = (sub - 1) & mask

# Iterate over set bits:
m = mask
while m:
    i = (m & -m).bit_length() - 1
    # use i
    m &= m - 1

CLASSIC PATTERN — TSP
---------------------
dp[mask][last] = min cost to visit cities in `mask` ending at `last`

Recurrence:
  dp[mask | (1 << next)][next] = min(dp[mask][last] + dist[last][next])

Final: min(dp[full_mask][last] + dist[last][0]) for all last

============================================================
"""
from functools import lru_cache


# ============================================================
# Pattern 1: Traveling Salesman Problem (TSP)
# Min cost cycle visiting all cities exactly once
# ============================================================
def tsp(dist):
    """O(N^2 * 2^N) — N cities, dist[i][j] = cost."""
    n = len(dist)
    INF = float("inf")
    # dp[mask][i] = min cost to visit cities in mask ending at i
    dp = [[INF] * n for _ in range(1 << n)]
    dp[1][0] = 0  # start at city 0, only city 0 visited

    for mask in range(1, 1 << n):
        if not (mask & 1):     # must include city 0
            continue
        for last in range(n):
            if not (mask & (1 << last)):
                continue
            if dp[mask][last] == INF:
                continue
            for nxt in range(n):
                if mask & (1 << nxt):
                    continue
                new_mask = mask | (1 << nxt)
                new_cost = dp[mask][last] + dist[last][nxt]
                if new_cost < dp[new_mask][nxt]:
                    dp[new_mask][nxt] = new_cost

    full = (1 << n) - 1
    return min(dp[full][i] + dist[i][0] for i in range(1, n))


# ============================================================
# Pattern 2: Assignment Problem
# N people, N jobs. cost[i][j] = cost of person i doing job j.
# Find min total cost.
# ============================================================
def assignment_problem(cost):
    """O(N * 2^N) using bitmask DP."""
    n = len(cost)

    @lru_cache(maxsize=None)
    def dp(person, mask):
        """Min cost to assign jobs to persons 0..person-1, using jobs in mask."""
        if person == n:
            return 0
        result = float("inf")
        for job in range(n):
            if not (mask & (1 << job)):
                continue
            new_mask = mask & ~(1 << job)
            result = min(result, cost[person][job] + dp(person + 1, new_mask))
        return result

    return dp(0, (1 << n) - 1)


# ============================================================
# Pattern 3: Count Hamilton Paths
# In directed graph, count paths visiting each vertex exactly once
# ============================================================
def count_hamilton_paths(n, edges):
    """O(N * 2^N) — graph has N nodes."""
    adj = [[False] * n for _ in range(n)]
    for u, v in edges:
        adj[u][v] = True

    @lru_cache(maxsize=None)
    def dp(mask, last):
        if mask == (1 << n) - 1:
            return 1
        total = 0
        for nxt in range(n):
            if mask & (1 << nxt):
                continue
            if not adj[last][nxt]:
                continue
            total += dp(mask | (1 << nxt), nxt)
        return total

    total = 0
    for start in range(n):
        total += dp(1 << start, start)
    return total


# ============================================================
# Pattern 4: Minimum Set Cover
# Given universe of N elements and sets, find min sets covering all
# ============================================================
def min_set_cover(n_elements, sets):
    """sets[i] = bitmask of which elements set i covers.
    Returns min number of sets to cover all elements."""
    full = (1 << n_elements) - 1
    INF = float("inf")

    @lru_cache(maxsize=None)
    def dp(covered):
        if covered == full:
            return 0
        result = INF
        for s in sets:
            if s & ~covered:  # this set adds new coverage
                result = min(result, 1 + dp(covered | s))
        return result

    return dp(0)


# ============================================================
# Pattern 5: Subset Sum Enumeration
# Iterate over all subsets of a mask
# ============================================================
def iterate_subsets(mask):
    """Demo: iterate over all non-empty subsets of mask."""
    subsets = []
    sub = mask
    while sub > 0:
        subsets.append(sub)
        sub = (sub - 1) & mask
    return subsets


# ============================================================
# Pattern 6: Partition into K Equal-Sum Subsets (LC 698)
# ============================================================
def can_partition_k_subsets(nums, k):
    total = sum(nums)
    if total % k != 0:
        return False
    target = total // k
    if max(nums) > target:
        return False
    n = len(nums)

    @lru_cache(maxsize=None)
    def dp(mask, current_sum):
        if mask == (1 << n) - 1:
            return True
        for i in range(n):
            if mask & (1 << i):
                continue
            new_sum = current_sum + nums[i]
            if new_sum > target:
                continue
            new_sum_mod = new_sum if new_sum < target else 0
            if dp(mask | (1 << i), new_sum_mod):
                return True
        return False

    return dp(0, 0)


# ============================================================
# Pattern 7: Shortest Path Visiting All Nodes (LC 847)
# Graph BFS + bitmask state
# ============================================================
from collections import deque


def shortest_path_visiting_all_nodes(graph):
    n = len(graph)
    full = (1 << n) - 1
    queue = deque()
    visited = set()
    for i in range(n):
        state = (1 << i, i)
        queue.append((state[0], i, 0))   # (mask, node, steps)
        visited.add(state)

    while queue:
        mask, node, steps = queue.popleft()
        if mask == full:
            return steps
        for nxt in graph[node]:
            new_mask = mask | (1 << nxt)
            if (new_mask, nxt) not in visited:
                visited.add((new_mask, nxt))
                queue.append((new_mask, nxt, steps + 1))
    return -1


# ============================================================
# Pattern 8: Number of Ways to Wear Different Hats (LC 1434)
# N people, 40 hat types. Each person likes some hats.
# Iterate over HATS not people (since hats > people usually)
# ============================================================
MOD = 10 ** 9 + 7


def ways_to_wear_hats(hats):
    """hats[i] = list of hats person i likes."""
    n = len(hats)
    # For each hat 1..40, list of people who like it
    hat_to_people = [[] for _ in range(41)]
    for person, likes in enumerate(hats):
        for h in likes:
            hat_to_people[h].append(person)

    full = (1 << n) - 1

    @lru_cache(maxsize=None)
    def dp(hat, mask):
        if mask == full:
            return 1
        if hat > 40:
            return 0
        # Option 1: skip this hat
        result = dp(hat + 1, mask)
        # Option 2: assign this hat to some person who likes it
        for p in hat_to_people[hat]:
            if not (mask & (1 << p)):
                result = (result + dp(hat + 1, mask | (1 << p))) % MOD
        return result

    return dp(1, 0)


# ============================================================
# Demo
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("PATTERN 1: TSP")
    print("=" * 60)
    dist = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0],
    ]
    print(f"  4-city TSP min cost: {tsp(dist)}  (expected 80)")

    print("\n" + "=" * 60)
    print("PATTERN 2: Assignment Problem")
    print("=" * 60)
    cost = [
        [9, 2, 7, 8],
        [6, 4, 3, 7],
        [5, 8, 1, 8],
        [7, 6, 9, 4],
    ]
    print(f"  Min assignment cost: {assignment_problem(cost)}  (expected 13)")

    print("\n" + "=" * 60)
    print("PATTERN 3: Hamilton Path Count")
    print("=" * 60)
    # 4 nodes, fully connected directed graph
    edges = [(i, j) for i in range(4) for j in range(4) if i != j]
    print(f"  4-node Kn count: {count_hamilton_paths(4, edges)}  (expected 24 = 4!)")

    print("\n" + "=" * 60)
    print("PATTERN 4: Min Set Cover")
    print("=" * 60)
    # Universe = {0,1,2,3,4}, sets covering subsets
    sets = (0b11100, 0b00111, 0b10101, 0b01010)
    print(f"  Min sets to cover universe: {min_set_cover(5, sets)}")

    print("\n" + "=" * 60)
    print("PATTERN 5: Subset Enumeration")
    print("=" * 60)
    mask = 0b1011
    subs = iterate_subsets(mask)
    print(f"  Non-empty subsets of {bin(mask)}: {[bin(s) for s in subs]}")

    print("\n" + "=" * 60)
    print("PATTERN 6: Partition into K Equal-Sum Subsets (LC 698)")
    print("=" * 60)
    nums = [4, 3, 2, 3, 5, 2, 1]
    k = 4
    print(f"  Can partition {nums} into {k}? {can_partition_k_subsets(nums, k)}")  # True

    print("\n" + "=" * 60)
    print("PATTERN 7: Shortest Path Visiting All Nodes (LC 847)")
    print("=" * 60)
    graph = [[1, 2, 3], [0], [0], [0]]
    print(f"  Min steps: {shortest_path_visiting_all_nodes(graph)}  (expected 4)")

    print("\n" + "=" * 60)
    print("PATTERN 8: Hat Assignments (LC 1434)")
    print("=" * 60)
    hats = [[3, 4], [4, 5], [5]]
    print(f"  Ways: {ways_to_wear_hats(hats)}  (expected 1)")

    print("\n" + "=" * 60)
    print("INTERVIEW Q&A")
    print("=" * 60)
    print("""
Q: Bitmask DP kab use karte ho?
A: N ≤ 20-22 + need to track subset of elements.
   Classic: TSP, assignment, set cover, Hamilton paths.

Q: Why N ≤ 20?
A: 2^20 = ~10^6 states. Larger crashes memory/time.
   For N=22, 2^22 = 4M still feasible if transitions cheap.

Q: How to iterate over subsets of a mask?
A: sub = mask; while sub > 0: ...; sub = (sub-1) & mask
   Total iterations across all masks = O(3^N).

Q: TSP complexity?
A: O(N^2 * 2^N). For N=20 → 20^2 * 10^6 = 4*10^8 — borderline.
   Add bitset tricks or pruning.

Q: Bitmask DP vs regular DP?
A: Bitmask = subset tracking. Regular = sequential decisions.
   Combine: bitmask + position is common.

Q: When iterate over hats vs people in LC 1434?
A: Iterate over the SMALLER dimension. People ≤ 10, hats = 40.
   So iterate hats but track people via mask.

Q: Memory issues at N=22?
A: 4M * 22 = 88M ints. Use array instead of dict.
   Or Python is slow — switch to C++ for tight contest problems.
""")
