"""
╔══════════════════════════════════════════════════════════════════╗
║                 GREEDY — Complete Theory Guide                   ║
╚══════════════════════════════════════════════════════════════════╝

WHAT IS GREEDY?
────────────────
A greedy algorithm makes the LOCALLY OPTIMAL choice at each step,
hoping to find the GLOBALLY OPTIMAL solution.

"Always pick the best option available right now, without looking back."

WHY IT WORKS (When It Does)?
──────────────────────────────
A greedy approach is CORRECT when:
  1. GREEDY CHOICE PROPERTY: A locally optimal choice leads to a globally optimal solution.
  2. OPTIMAL SUBSTRUCTURE: Optimal solution contains optimal subsolutions.

PROVING GREEDY IS CORRECT — Exchange Argument:
  Assume optimal solution differs from greedy. Show we can "exchange"
  the difference to make it match greedy without making it worse.
  Therefore greedy is also optimal.

GREEDY vs DP:
  Greedy: O(n log n) or O(n), makes ONE choice per step (no trying alternatives).
  DP: O(n²) or more, considers ALL choices via table.
  When greedy fails: use DP.

CLASSIC GREEDY PATTERNS:
─────────────────────────────────────────────────────────────────
Pattern                   Example Problem
─────────────────────────────────────────────────────────────────
Interval Scheduling       Activity Selection, Meeting Rooms
Array Partitioning        Jump Game, Partition Labels
Greedy BFS/Reach          Gas Station, Two City Scheduling
Counting/Frequency        Task Scheduler, Reorganize String
Custom Sort               Largest Number, Hand of Straights
─────────────────────────────────────────────────────────────────
"""

from typing import List
from collections import Counter

# ─────────────────────────────────────────────
# 1. INTERVAL SCHEDULING — Classic Greedy
# ─────────────────────────────────────────────
print("=" * 60)
print("1. INTERVAL SCHEDULING (Activity Selection)")
print("=" * 60)

"""
PROBLEM: Given n activities with start/end times, select the maximum
number of non-overlapping activities.

GREEDY CHOICE: Always select the activity that ENDS EARLIEST.
Why? Ending early leaves maximum room for future activities.

PROOF (Exchange Argument):
  Suppose optimal picks activity A instead of greedy's B (earliest end).
  B ends no later than A. So replacing A with B doesn't create conflicts.
  We can always swap to greedy's choice without losing activities.
"""

def max_activities(intervals: List[List[int]]) -> int:
    """Maximum non-overlapping intervals."""
    intervals.sort(key=lambda x: x[1])  # sort by end time
    count = 0
    last_end = float('-inf')
    for start, end in intervals:
        if start >= last_end:
            count += 1
            last_end = end
    return count

intervals = [[1,4],[3,5],[0,6],[5,7],[3,8],[5,9],[6,10],[8,11],[8,12],[2,13],[12,14]]
print(f"Max non-overlapping activities: {max_activities(intervals)}")  # 4

# ─────────────────────────────────────────────
# 2. JUMP GAME — Greedy Reach
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("2. JUMP GAME — Greedy Max Reach")
print("=" * 60)

"""
Track the maximum reachable index as we scan left to right.
If we can't reach position i, we're stuck.
"""

def can_jump(nums: List[int]) -> bool:
    max_reach = 0
    for i, jump in enumerate(nums):
        if i > max_reach:
            return False  # can't reach here
        max_reach = max(max_reach, i + jump)
    return True

print(f"[2,3,1,1,4]: {can_jump([2,3,1,1,4])}")  # True
print(f"[3,2,1,0,4]: {can_jump([3,2,1,0,4])}")  # False

# ─────────────────────────────────────────────
# 3. MINIMUM JUMPS (GREEDY BFS)
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("3. MINIMUM JUMPS — BFS-Style Greedy")
print("=" * 60)

"""
Jump Game II: Minimum jumps to reach the end.
Greedy: At each jump, choose the option that extends the reach the furthest.
Think of it as BFS levels: current jump covers [curr_start, curr_end],
the next jump can reach anything in [curr_end+1, max_reach].
"""

def min_jumps(nums: List[int]) -> int:
    jumps = 0
    curr_end = 0    # boundary of current jump range
    max_reach = 0   # furthest reachable from current range

    for i in range(len(nums) - 1):
        max_reach = max(max_reach, i + nums[i])
        if i == curr_end:           # must jump now
            jumps += 1
            curr_end = max_reach
    return jumps

print(f"Min jumps [2,3,1,1,4]: {min_jumps([2,3,1,1,4])}")  # 2
print(f"Min jumps [2,3,0,1,4]: {min_jumps([2,3,0,1,4])}")  # 2

# ─────────────────────────────────────────────
# 4. GAS STATION — Greedy
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("4. GAS STATION — Greedy Invariant")
print("=" * 60)

"""
KEY INSIGHTS:
1. If sum(gas) >= sum(cost), a solution ALWAYS exists.
2. If we fail at station i starting from station j,
   then starting from ANY station in [j, i] also fails.
   So try starting from i+1.

This avoids O(n²) brute force.
"""

def can_complete_circuit(gas: List[int], cost: List[int]) -> int:
    total_surplus = 0
    curr_surplus = 0
    start = 0

    for i in range(len(gas)):
        total_surplus += gas[i] - cost[i]
        curr_surplus += gas[i] - cost[i]
        if curr_surplus < 0:
            start = i + 1   # can't start from anywhere in [prev_start, i]
            curr_surplus = 0

    return start if total_surplus >= 0 else -1

print(f"Gas station: {can_complete_circuit([1,2,3,4,5],[3,4,5,1,2])}")  # 3
print(f"Gas station: {can_complete_circuit([2,3,4],[3,4,3])}")           # -1

# ─────────────────────────────────────────────
# 5. PARTITION LABELS — Greedy
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("5. PARTITION LABELS — Last Occurrence Greedy")
print("=" * 60)

"""
Greedily extend the current partition to include all occurrences
of each character seen. When we reach the end of the current partition
window, close it and start a new one.
"""

def partition_labels(s: str) -> List[int]:
    last = {c: i for i, c in enumerate(s)}  # last occurrence of each char
    result = []
    start = end = 0

    for i, c in enumerate(s):
        end = max(end, last[c])  # extend window to include all c's
        if i == end:             # reached the end of current partition
            result.append(end - start + 1)
            start = i + 1

    return result

print(f"Partition labels 'ababcbacadefegdehijhklij': {partition_labels('ababcbacadefegdehijhklij')}")
# [9, 7, 8]

# ─────────────────────────────────────────────
# 6. HUFFMAN CODING CONCEPT
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("6. HUFFMAN CODING — Greedy Min-Cost Tree")
print("=" * 60)

huffman_explanation = """
Huffman Coding assigns shorter codes to more frequent characters.
Greedy: Always merge the two LOWEST frequency nodes.

Algorithm:
1. Create leaf node for each character with its frequency.
2. Build a min heap.
3. Repeat until one node remains:
   a. Extract two minimum-frequency nodes.
   b. Create new internal node with frequency = sum.
   c. Insert back into heap.

This gives optimal prefix-free encoding.
Greedy proof: Merging least frequent nodes first minimizes total depth
(exchange argument — any other order produces worse total cost).
"""
print(huffman_explanation)

# ─────────────────────────────────────────────
# 7. WHEN GREEDY FAILS
# ─────────────────────────────────────════════
print("=" * 60)
print("7. WHEN GREEDY FAILS — Use DP Instead")
print("=" * 60)

comparison = """
GREEDY WORKS:               GREEDY FAILS (USE DP):
─────────────────────────── ──────────────────────────
Activity Selection          0/1 Knapsack
Coin Change (certain sets)  Coin Change (general coins)
Dijkstra's Shortest Path    Floyd-Warshall (negative edges)
Huffman Coding              General coding problems
Interval Scheduling         Weighted interval scheduling

COIN CHANGE EXAMPLE:
  Coins = [1, 3, 4], amount = 6
  Greedy: 4 + 1 + 1 = 3 coins ← WRONG!
  DP: 3 + 3 = 2 coins ← CORRECT

The greedy choice (largest coin first) doesn't lead to optimal
when coin denominations are non-standard. DP is needed.
"""
print(comparison)

# ─────────────────────────────────────────────
# 8. INTERVIEW Q&A
# ─────────────────────────────────────────────
print("=" * 60)
print("INTERVIEW Q&A")
print("=" * 60)

qa = """
Q1: How do you prove a greedy algorithm is correct?
A1: Two main techniques:
    1. Greedy stays ahead: Show greedy's solution is at least as good as
       any other at every step.
    2. Exchange argument: Assume another solution is optimal. Show we can
       swap any difference with greedy's choice without worsening the result.
       Therefore greedy is also optimal.

Q2: What's the difference between greedy and DP?
A2: Greedy makes ONE irrevocable choice at each step. O(n) or O(n log n).
    DP considers ALL choices, remembers past results. O(n²) or more.
    Greedy is correct for problems with greedy choice property.
    DP is needed when greedy fails (no greedy choice property).

Q3: Why does sorting by end time work for interval scheduling?
A3: It maximizes the remaining time for future activities. Choosing the
    earliest-ending activity leaves the most room after it.
    Exchange argument: Any optimal solution can be transformed into
    the greedy solution without reducing the number of activities.

Q4: Is Dijkstra's algorithm greedy?
A4: Yes! At each step, it greedily picks the unvisited node with the
    smallest tentative distance. Works because edge weights are non-negative
    (no shorter path can be found through a longer intermediate path).

Q5: Can a problem have both greedy and DP solutions?
A5: Yes. For example, interval scheduling can be solved greedily in O(n log n)
    or with DP in O(n²). Greedy is preferred when it works.

Q6: What makes coin change different from a greedy-solvable coin problem?
A6: Standard coins (1,5,10,25) happen to have the greedy property.
    Arbitrary coin sets don't. For [1,3,4], greedy picks 4 for amount 6,
    then needs 1+1 → 3 coins. DP finds 3+3 → 2 coins.
    Greedy works only when each larger coin is a multiple of smaller ones.
"""
print(qa)
