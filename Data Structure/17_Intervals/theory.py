"""
17 — Intervals — Theory
========================
Level: Intermediate
"""
from __future__ import annotations
from typing import List
import heapq

# ════════════════════════════════════════════════════════════
# WHAT & WHY
# ════════════════════════════════════════════════════════════
"""
INTERVAL = [start, end] representing a contiguous range.

WHEN TO USE:
  - Calendar/scheduling problems (meeting rooms, free time)
  - Time-range queries (find overlapping events)
  - Merging ranges (IP ranges, code coverage)
  - Resource allocation (CPU bursts, disk I/O)

OVERLAP CONDITION (key insight):
  Two intervals [a, b] and [c, d] overlap if:
      a <= d  AND  c <= b
  They do NOT overlap if:
      b < c  (first ends before second starts)
      d < a  (second ends before first starts)
"""

# ════════════════════════════════════════════════════════════
# COMPLEXITY
# ════════════════════════════════════════════════════════════
"""
Operation                      Time        Space
──────────────────────────────────────────────────
Sort intervals                 O(n log n)  O(1)
Merge intervals                O(n log n)  O(n)
Insert interval                O(n)        O(n)
Meeting Rooms I (overlap?)     O(n log n)  O(1)
Meeting Rooms II (min rooms)   O(n log n)  O(n)
Sweep line (max overlap)       O(n log n)  O(n)
Interval scheduling (greedy)   O(n log n)  O(1)
Interval intersections         O(n + m)    O(1)
"""

# ════════════════════════════════════════════════════════════
# OVERLAP HELPERS
# ════════════════════════════════════════════════════════════

def overlaps(a: List[int], b: List[int]) -> bool:
    """True if interval a and b overlap."""
    return a[0] <= b[1] and b[0] <= a[1]

def contains(outer: List[int], inner: List[int]) -> bool:
    """True if outer fully contains inner."""
    return outer[0] <= inner[0] and inner[1] <= outer[1]


# ════════════════════════════════════════════════════════════
# PATTERN 1: Sort + Merge
# ════════════════════════════════════════════════════════════

def merge_intervals(intervals: List[List[int]]) -> List[List[int]]:
    """
    Merge all overlapping intervals.
    Key: sort by start, extend end when overlap found.
    O(n log n) time, O(n) space.
    """
    if not intervals:
        return []
    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0][:]]  # copy first interval

    for start, end in intervals[1:]:
        if start <= merged[-1][1]:           # overlaps with last merged
            merged[-1][1] = max(merged[-1][1], end)   # extend end
        else:
            merged.append([start, end])      # no overlap → new interval

    return merged

print("Merge:", merge_intervals([[1,3],[2,6],[8,10],[15,18]]))  # [[1,6],[8,10],[15,18]]


# ════════════════════════════════════════════════════════════
# PATTERN 2: Insert Interval (already sorted, no resort needed)
# ════════════════════════════════════════════════════════════

def insert_interval(intervals: List[List[int]], new_interval: List[int]) -> List[List[int]]:
    """
    Insert new_interval into sorted non-overlapping list.
    3-phase scan: before / overlapping / after.
    O(n) time.
    """
    result = []
    i, n = 0, len(intervals)

    # Phase 1: add all intervals that end before new_interval starts
    while i < n and intervals[i][1] < new_interval[0]:
        result.append(intervals[i])
        i += 1

    # Phase 2: merge all overlapping intervals into new_interval
    while i < n and intervals[i][0] <= new_interval[1]:
        new_interval[0] = min(new_interval[0], intervals[i][0])
        new_interval[1] = max(new_interval[1], intervals[i][1])
        i += 1
    result.append(new_interval)

    # Phase 3: add remaining intervals
    while i < n:
        result.append(intervals[i])
        i += 1

    return result

print("Insert:", insert_interval([[1,2],[3,5],[6,7],[8,10],[12,16]], [4,8]))
# [[1,2],[3,10],[12,16]]


# ════════════════════════════════════════════════════════════
# PATTERN 3: Meeting Rooms — Can attend all? (adjacent overlap check)
# ════════════════════════════════════════════════════════════

def can_attend_all(intervals: List[List[int]]) -> bool:
    """
    True if no two meetings overlap.
    Sort by start, check if any start < previous end.
    O(n log n) time, O(1) space.
    """
    intervals.sort(key=lambda x: x[0])
    for i in range(1, len(intervals)):
        if intervals[i][0] < intervals[i-1][1]:   # starts before previous ends
            return False
    return True

print("Can attend all:", can_attend_all([[0,30],[5,10],[15,20]]))  # False


# ════════════════════════════════════════════════════════════
# PATTERN 4: Meeting Rooms II — Min rooms needed (min-heap)
# ════════════════════════════════════════════════════════════

def min_meeting_rooms(intervals: List[List[int]]) -> int:
    """
    Min conference rooms for all meetings.
    Heap stores end times of ongoing meetings.
    Heap size at end = answer.
    O(n log n) time, O(n) space.
    """
    if not intervals:
        return 0
    intervals.sort(key=lambda x: x[0])
    heap = []  # min-heap of end times

    for start, end in intervals:
        if heap and heap[0] <= start:
            # Reuse room (meeting ended before this starts)
            heapq.heapreplace(heap, end)
        else:
            # Need new room
            heapq.heappush(heap, end)

    return len(heap)

print("Min rooms:", min_meeting_rooms([[0,30],[5,10],[15,20]]))  # 2


# ════════════════════════════════════════════════════════════
# PATTERN 5: Sweep Line — Max simultaneous overlap
# ════════════════════════════════════════════════════════════

def max_simultaneous_overlap(intervals: List[List[int]]) -> int:
    """
    Maximum number of intervals overlapping at any point.
    Events: +1 at start, -1 at end.
    O(n log n) time, O(n) space.

    Tie-breaking: end events (-1) before start events (+1)
    for non-overlapping [1,3],[3,5] to count correctly.
    """
    events = []
    for start, end in intervals:
        events.append((start, 1))    # interval starts
        events.append((end, -1))     # interval ends

    # Sort: by time; ties: end (-1) before start (+1) if they share a time
    events.sort(key=lambda x: (x[0], x[1]))

    max_overlap = curr = 0
    for time, delta in events:
        curr += delta
        max_overlap = max(max_overlap, curr)
    return max_overlap

print("Max overlap:", max_simultaneous_overlap([[1,4],[2,5],[3,6]]))  # 3


# ════════════════════════════════════════════════════════════
# PATTERN 6: Interval Scheduling (Greedy — sort by END)
# ════════════════════════════════════════════════════════════

def max_non_overlapping(intervals: List[List[int]]) -> int:
    """
    Maximum number of non-overlapping intervals we can select.
    Greedy: always pick interval with earliest END time.
    WHY sort by end? Keeps future as open as possible.
    O(n log n) time, O(1) space.
    """
    intervals.sort(key=lambda x: x[1])  # sort by END (not start!)
    count = 0
    last_end = float('-inf')

    for start, end in intervals:
        if start >= last_end:       # doesn't overlap with last selected
            count += 1
            last_end = end

    return count

print("Max non-overlapping:", max_non_overlapping([[1,2],[2,3],[3,4],[1,3]]))  # 3


# ════════════════════════════════════════════════════════════
# PATTERN 7: Two Pointers — Interval Intersections
# ════════════════════════════════════════════════════════════

def interval_intersections(A: List[List[int]], B: List[List[int]]) -> List[List[int]]:
    """
    Find all intersections of two sorted interval lists.
    Two pointers: advance the one with smaller end time.
    O(n + m) time, O(1) space.
    """
    result = []
    i = j = 0

    while i < len(A) and j < len(B):
        lo = max(A[i][0], B[j][0])
        hi = min(A[i][1], B[j][1])
        if lo <= hi:
            result.append([lo, hi])
        # advance pointer with smaller end
        if A[i][1] < B[j][1]:
            i += 1
        else:
            j += 1

    return result

print("Intersections:", interval_intersections([[0,2],[5,10],[13,23],[24,25]],
                                               [[1,5],[8,12],[15,24],[25,26]]))


# ════════════════════════════════════════════════════════════
# WHY SORT BY END FOR SCHEDULING vs START FOR MERGING
# ════════════════════════════════════════════════════════════
"""
MERGE INTERVALS → sort by START
  Reason: To detect overlaps, we need to know when each interval begins.
  If the current start <= previous end → overlap → extend end.

INTERVAL SCHEDULING (max non-overlapping) → sort by END
  Reason: Greedy exchange argument. If we pick the interval ending earliest,
  we leave maximum room for future intervals. Picking a later-ending interval
  can only block more future intervals. This is provably optimal.

MEETING ROOMS II (min rooms) → sort by START
  Reason: We process meetings in order of arrival. The heap stores end times
  of ongoing meetings. If earliest-ending meeting is done before new one starts
  → reuse that room. Otherwise → new room.
"""

# ════════════════════════════════════════════════════════════
# INTERVIEW Q&A
# ════════════════════════════════════════════════════════════
"""
Q1: Why sort by start for merge but by end for scheduling?
A: Merge needs to detect overlap with previous → needs chronological order by start.
   Scheduling (greedy) needs to maximize future options → pick earliest-ending first.

Q2: What is the two-pointer approach for interval intersection?
A: Both lists are sorted. At each step, compute overlap of current pair.
   Advance the pointer whose interval ends earlier (it can't overlap future intervals
   from the other list). O(n+m), better than O(n*m) brute force.

Q3: How does the sweep line work for Meeting Rooms II?
A: Convert each [start,end] to two events: (start, +1) and (end, -1).
   Sort events. Scan: running sum = current rooms in use. Peak = answer.
   Tie-breaking: process end before start at same time (non-overlapping meetings
   sharing a boundary shouldn't count as simultaneous).

Q4: What data structure for Meeting Rooms II with heap approach?
A: Min-heap of end times (ongoing meetings). For each new meeting:
   - If heap[0] (earliest ending) <= new start → reuse that room (heapreplace).
   - Else → add new room (heappush). Final heap size = answer.

Q5: How to find all free time slots given employee schedules?
A: Merge all intervals across employees → one list. Sort. Gaps between merged
   intervals = free time. (LC 759 Employee Free Time)

Q6: Difference between open [a,b) and closed [a,b] intervals?
A: For closed: overlap if a1<=b2 AND a2<=b1.
   For half-open [a,b): overlap if a1<b2 AND a2<b1. Adjust comparisons.

Q7: How to insert an interval into a sorted list efficiently?
A: Binary search for insertion point. Then merge with neighbors.
   Or: 3-phase scan O(n) — add non-overlapping left, merge middle, add right.

Q8: Can Kadane's algorithm be adapted for intervals?
A: Not directly. Kadane's is for maximum subarray sum. Interval problems use
   sorting + scanning. However prefix sum on events (sweep line) is analogous.

Q9: What is the greedy exchange argument for interval scheduling?
A: Suppose optimal solution picks interval X instead of our greedy choice G (G ends
   earlier). Replace X with G: new solution still valid (G ends ≤ X ends, so no new
   conflicts introduced) and has same count. Therefore greedy ≥ optimal. QED.

Q10: Time complexity of finding if any two intervals in a set overlap?
A: O(n log n) — sort by start, check adjacent pairs. If any start[i] < end[i-1] → overlap.
   Better than O(n²) brute force.
"""
