"""
╔══════════════════════════════════════════════════════════════════╗
║               GREEDY — 10 LeetCode-Style Problems                ║
╚══════════════════════════════════════════════════════════════════╝
"""

from typing import List
from collections import Counter
import heapq

# ══════════════════════════════════════════════════════════════════
# Problem 1: Jump Game (LC 55)
# ══════════════════════════════════════════════════════════════════
def canJump(nums: List[int]) -> bool:
    """
    Can you reach the last index? nums[i] = max jump distance from i.

    Greedy: Track maximum reachable index. If we encounter position i
    beyond max_reach, we're stuck.

    Example:
      [2,3,1,1,4] → True
      [3,2,1,0,4] → False
    """
    max_reach = 0
    for i, jump in enumerate(nums):
        if i > max_reach:
            return False
        max_reach = max(max_reach, i + jump)
    return True

print("=== Jump Game ===")
print(canJump([2,3,1,1,4]))  # True
print(canJump([3,2,1,0,4]))  # False
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 2: Jump Game II (LC 45)
# ══════════════════════════════════════════════════════════════════
def jump(nums: List[int]) -> int:
    """
    Minimum number of jumps to reach the last index.

    Greedy BFS approach: Track current window [0..curr_end].
    When i reaches curr_end, we must jump. The next window extends to max_reach.
    Count jumps (= BFS levels).

    Example:
      [2,3,1,1,4] → 2  (jump 2 steps, then 3 steps)
      [2,3,0,1,4] → 2
    """
    jumps = curr_end = max_reach = 0
    for i in range(len(nums) - 1):
        max_reach = max(max_reach, i + nums[i])
        if i == curr_end:
            jumps += 1
            curr_end = max_reach
    return jumps

print("\n=== Jump Game II ===")
print(jump([2,3,1,1,4]))  # 2
print(jump([2,3,0,1,4]))  # 2
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 3: Gas Station (LC 134)
# ══════════════════════════════════════════════════════════════════
def canCompleteCircuit(gas: List[int], cost: List[int]) -> int:
    """
    n gas stations in a circle. gas[i] available at i, cost[i] to travel to i+1.
    Find starting station to complete the circuit, or -1 if impossible.

    Greedy: If total gas >= total cost, a solution exists.
    If we can't reach station i from start j, any station in [j, i] also fails.
    Reset start to i+1.

    Example:
      gas=[1,2,3,4,5], cost=[3,4,5,1,2] → 3
      gas=[2,3,4], cost=[3,4,3] → -1
    """
    total = curr = start = 0
    for i in range(len(gas)):
        diff = gas[i] - cost[i]
        total += diff
        curr += diff
        if curr < 0:
            start = i + 1
            curr = 0
    return start if total >= 0 else -1

print("\n=== Gas Station ===")
print(canCompleteCircuit([1,2,3,4,5],[3,4,5,1,2]))  # 3
print(canCompleteCircuit([2,3,4],[3,4,3]))           # -1
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 4: Hand of Straights (LC 846)
# ══════════════════════════════════════════════════════════════════
def isNStraightHand(hand: List[int], groupSize: int) -> bool:
    """
    Can you arrange 'hand' into groups of 'groupSize' consecutive cards?

    Greedy: Process groups starting from the smallest card.
    Use a min-heap + counter. At each step, form a group starting at heap[0].

    Example:
      hand=[1,2,3,6,2,3,4,7,8], groupSize=3 → True
      hand=[1,2,3,4,5], groupSize=4 → False
    """
    if len(hand) % groupSize != 0:
        return False
    count = Counter(hand)
    min_heap = list(count.keys())
    heapq.heapify(min_heap)

    while min_heap:
        start = min_heap[0]
        for i in range(start, start + groupSize):
            if count[i] == 0:
                return False
            count[i] -= 1
            if count[i] == 0:
                if i != min_heap[0]:
                    return False
                heapq.heappop(min_heap)
    return True

print("\n=== Hand of Straights ===")
print(isNStraightHand([1,2,3,6,2,3,4,7,8], 3))  # True
print(isNStraightHand([1,2,3,4,5], 4))           # False
# Time: O(n log n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 5: Merge Triplets to Form Target (LC 1899)
# ══════════════════════════════════════════════════════════════════
def mergeTriplets(triplets: List[List[int]], target: List[int]) -> bool:
    """
    Merge (max each component) any triplets to form target.
    Discard triplets that have any component exceeding target.

    Greedy: After filtering, check if OR/max of remaining triplets = target.

    Example:
      triplets=[[2,5,3],[1,8,4],[1,7,5]], target=[2,7,5] → True
      triplets=[[3,4,5],[4,5,6]], target=[3,2,5] → False
    """
    result = [0, 0, 0]
    for t in triplets:
        if t[0] <= target[0] and t[1] <= target[1] and t[2] <= target[2]:
            result[0] = max(result[0], t[0])
            result[1] = max(result[1], t[1])
            result[2] = max(result[2], t[2])
    return result == target

print("\n=== Merge Triplets to Form Target ===")
print(mergeTriplets([[2,5,3],[1,8,4],[1,7,5]], [2,7,5]))  # True
print(mergeTriplets([[3,4,5],[4,5,6]], [3,2,5]))           # False
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 6: Partition Labels (LC 763)
# ══════════════════════════════════════════════════════════════════
def partitionLabels(s: str) -> List[int]:
    """
    Partition s into maximum parts where each letter appears in at most one part.
    Return list of part sizes.

    Greedy: Last occurrence of each char. Extend current partition to include
    all occurrences of each char seen. When we reach the boundary, close part.

    Example:
      "ababcbacadefegdehijhklij" → [9,7,8]
    """
    last = {c: i for i, c in enumerate(s)}
    result = []
    start = end = 0
    for i, c in enumerate(s):
        end = max(end, last[c])
        if i == end:
            result.append(end - start + 1)
            start = i + 1
    return result

print("\n=== Partition Labels ===")
print(partitionLabels("ababcbacadefegdehijhklij"))  # [9,7,8]
print(partitionLabels("eccbbbbdec"))                 # [10]
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 7: Valid Parenthesis String (LC 678)
# ══════════════════════════════════════════════════════════════════
def checkValidString(s: str) -> bool:
    """
    '(' is open, ')' is close, '*' can be '(', ')', or ''.
    Determine if string can be valid.

    Greedy: Track range [lo, hi] = possible open paren counts.
    - '(': lo++, hi++
    - ')': lo--, hi--
    - '*': lo-- (treat as ')' or ''), hi++ (treat as '(')
    If hi < 0: too many ')' → False.
    Clamp lo to 0 (can't have negative open count).
    At end: lo == 0 means valid balance is achievable.

    Example: "(*)" → True  "(*))" → True  "(**)" → True
    """
    lo = hi = 0
    for c in s:
        if c == '(':
            lo += 1; hi += 1
        elif c == ')':
            lo -= 1; hi -= 1
        else:  # '*'
            lo -= 1; hi += 1
        if hi < 0: return False  # impossible to close
        lo = max(lo, 0)          # can't go below 0
    return lo == 0

print("\n=== Valid Parenthesis String ===")
print(checkValidString("(*)"))   # True
print(checkValidString("(*))"))  # True
print(checkValidString("(**(")) # False
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 8: Non-overlapping Intervals (LC 435)
# ══════════════════════════════════════════════════════════════════
def eraseOverlapIntervals(intervals: List[List[int]]) -> int:
    """
    Minimum number of intervals to remove so none overlap.
    = n - (maximum non-overlapping intervals).

    Greedy: Sort by end. Keep interval with earliest end.
    If overlap, remove the one with later end (don't update last_end).

    Example:
      [[1,2],[2,3],[3,4],[1,3]] → 1 (remove [1,3])
      [[1,2],[1,2],[1,2]] → 2
    """
    intervals.sort(key=lambda x: x[1])
    removals = 0
    prev_end = float('-inf')
    for start, end in intervals:
        if start >= prev_end:
            prev_end = end
        else:
            removals += 1  # remove this interval (it extends further)
    return removals

print("\n=== Non-overlapping Intervals ===")
print(eraseOverlapIntervals([[1,2],[2,3],[3,4],[1,3]]))  # 1
print(eraseOverlapIntervals([[1,2],[1,2],[1,2]]))         # 2
print(eraseOverlapIntervals([[1,2],[2,3]]))               # 0
# Time: O(n log n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 9: Assign Cookies (LC 455)
# ══════════════════════════════════════════════════════════════════
def findContentChildren(g: List[int], s: List[int]) -> int:
    """
    Assign cookies to children. Child i needs cookie of size >= g[i].
    Each child gets at most one cookie. Maximize content children.

    Greedy: Sort both. Match smallest sufficient cookie to each child.

    Example:
      g=[1,2,3], s=[1,1] → 1
      g=[1,2], s=[1,2,3] → 2
    """
    g.sort(); s.sort()
    child = cookie = 0
    while child < len(g) and cookie < len(s):
        if s[cookie] >= g[child]:
            child += 1
        cookie += 1
    return child

print("\n=== Assign Cookies ===")
print(findContentChildren([1,2,3], [1,1]))    # 1
print(findContentChildren([1,2], [1,2,3]))    # 2
# Time: O(n log n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 10: Minimum Number of Arrows to Burst Balloons (LC 452)
# ══════════════════════════════════════════════════════════════════
def findMinArrowShots(points: List[List[int]]) -> int:
    """
    Balloons span [start, end]. An arrow at x bursts all balloons with start <= x <= end.
    Find minimum arrows to burst all balloons.

    Greedy: Sort by END. Arrow at the end of the first balloon.
    This bursts all balloons overlapping with it.
    When we find a balloon that starts AFTER current arrow, shoot a new arrow.

    This is equivalent to: minimum number of groups of overlapping intervals.

    Example:
      [[10,16],[2,8],[1,6],[7,12]] → 2
      [[1,2],[3,4],[5,6],[7,8]] → 4
      [[1,2],[2,3],[3,4],[4,5]] → 2
    """
    points.sort(key=lambda x: x[1])  # sort by end
    arrows = 1
    arrow_pos = points[0][1]

    for start, end in points[1:]:
        if start > arrow_pos:   # this balloon is not hit by current arrow
            arrows += 1
            arrow_pos = end

    return arrows

print("\n=== Minimum Arrows to Burst Balloons ===")
print(findMinArrowShots([[10,16],[2,8],[1,6],[7,12]]))  # 2
print(findMinArrowShots([[1,2],[3,4],[5,6],[7,8]]))     # 4
print(findMinArrowShots([[1,2],[2,3],[3,4],[4,5]]))     # 2
# Time: O(n log n) | Space: O(1)

print("\n✓ All 10 Greedy problems solved!")
