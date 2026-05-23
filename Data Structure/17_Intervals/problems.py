"""17 — Intervals — Problems | 10 problems | Easy→Hard"""
from typing import List
import heapq
from sortedcontainers import SortedList  # pip install sortedcontainers

# ─────────────────────────────────────────────
# P01. Merge Intervals  [Medium][LC 56]
# ─────────────────────────────────────────────
"""
Input: [[1,3],[2,6],[8,10],[15,18]]
Output: [[1,6],[8,10],[15,18]]
"""
def merge(intervals: List[List[int]]) -> List[List[int]]:
    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0][:]]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged

print("P01:", merge([[1,3],[2,6],[8,10],[15,18]]))  # [[1,6],[8,10],[15,18]]


# ─────────────────────────────────────────────
# P02. Insert Interval  [Medium][LC 57]
# ─────────────────────────────────────────────
"""
Insert newInterval into sorted non-overlapping intervals.
Input: [[1,2],[3,5],[6,7],[8,10],[12,16]], newInterval=[4,8]
Output: [[1,2],[3,10],[12,16]]
"""
def insert(intervals: List[List[int]], newInterval: List[int]) -> List[List[int]]:
    result = []
    i, n = 0, len(intervals)
    # Before new interval
    while i < n and intervals[i][1] < newInterval[0]:
        result.append(intervals[i]); i += 1
    # Merge overlapping
    while i < n and intervals[i][0] <= newInterval[1]:
        newInterval[0] = min(newInterval[0], intervals[i][0])
        newInterval[1] = max(newInterval[1], intervals[i][1])
        i += 1
    result.append(newInterval)
    # After new interval
    while i < n:
        result.append(intervals[i]); i += 1
    return result

print("P02:", insert([[1,2],[3,5],[6,7],[8,10],[12,16]], [4,8]))  # [[1,2],[3,10],[12,16]]


# ─────────────────────────────────────────────
# P03. Meeting Rooms  [Easy][LC 252]
# ─────────────────────────────────────────────
"""
Can a person attend all meetings (no overlaps)?
Input: [[0,30],[5,10],[15,20]]  Output: False
"""
def canAttendMeetings(intervals: List[List[int]]) -> bool:
    intervals.sort(key=lambda x: x[0])
    for i in range(1, len(intervals)):
        if intervals[i][0] < intervals[i-1][1]:
            return False
    return True

print("P03:", canAttendMeetings([[0,30],[5,10],[15,20]]))  # False
print("P03:", canAttendMeetings([[7,10],[2,4]]))           # True


# ─────────────────────────────────────────────
# P04. Meeting Rooms II  [Medium][LC 253]
# ─────────────────────────────────────────────
"""
Minimum conference rooms required.
Input: [[0,30],[5,10],[15,20]]  Output: 2
"""
def minMeetingRooms(intervals: List[List[int]]) -> int:
    if not intervals: return 0
    intervals.sort(key=lambda x: x[0])
    heap = []  # min-heap of end times
    for start, end in intervals:
        if heap and heap[0] <= start:
            heapq.heapreplace(heap, end)  # reuse room
        else:
            heapq.heappush(heap, end)     # new room
    return len(heap)

print("P04:", minMeetingRooms([[0,30],[5,10],[15,20]]))  # 2
print("P04:", minMeetingRooms([[7,10],[2,4]]))           # 1


# ─────────────────────────────────────────────
# P05. Non-overlapping Intervals  [Medium][LC 435]
# ─────────────────────────────────────────────
"""
Min number of intervals to remove to make rest non-overlapping.
Input: [[1,2],[2,3],[3,4],[1,3]]  Output: 1 (remove [1,3])
Strategy: max non-overlapping = sort by end, greedy pick.
Answer = n - max_non_overlapping.
"""
def eraseOverlapIntervals(intervals: List[List[int]]) -> int:
    intervals.sort(key=lambda x: x[1])  # sort by END
    count = 0      # non-overlapping count
    last_end = float('-inf')
    for start, end in intervals:
        if start >= last_end:
            count += 1
            last_end = end
        # else: skip this interval (remove it)
    return len(intervals) - count

print("P05:", eraseOverlapIntervals([[1,2],[2,3],[3,4],[1,3]]))  # 1
print("P05:", eraseOverlapIntervals([[1,2],[1,2],[1,2]]))        # 2


# ─────────────────────────────────────────────
# P06. Minimum Number of Arrows to Burst Balloons  [Medium][LC 452]
# ─────────────────────────────────────────────
"""
Balloons as intervals on x-axis. Arrow shot at x hits all balloons with xstart<=x<=xend.
Minimum arrows to burst all balloons.
Input: [[10,16],[2,8],[1,6],[7,12]]  Output: 2
Strategy: same as interval scheduling — sort by end, count groups.
"""
def findMinArrowShots(points: List[List[int]]) -> int:
    points.sort(key=lambda x: x[1])  # sort by end
    arrows = 0
    arrow_pos = float('-inf')
    for start, end in points:
        if start > arrow_pos:     # current arrow misses this balloon
            arrows += 1
            arrow_pos = end       # shoot arrow at this balloon's end
    return arrows

print("P06:", findMinArrowShots([[10,16],[2,8],[1,6],[7,12]]))  # 2
print("P06:", findMinArrowShots([[1,2],[3,4],[5,6],[7,8]]))     # 4


# ─────────────────────────────────────────────
# P07. Interval List Intersections  [Medium][LC 986]
# ─────────────────────────────────────────────
"""
Two sorted lists of closed intervals. Return intersection.
Input: A=[[0,2],[5,10],[13,23],[24,25]], B=[[1,5],[8,12],[15,24],[25,26]]
Output: [[1,2],[5,5],[8,10],[15,23],[24,24],[25,25]]
"""
def intervalIntersection(firstList: List[List[int]], secondList: List[List[int]]) -> List[List[int]]:
    result = []
    i = j = 0
    while i < len(firstList) and j < len(secondList):
        lo = max(firstList[i][0], secondList[j][0])
        hi = min(firstList[i][1], secondList[j][1])
        if lo <= hi:
            result.append([lo, hi])
        if firstList[i][1] < secondList[j][1]:
            i += 1
        else:
            j += 1
    return result

print("P07:", intervalIntersection([[0,2],[5,10],[13,23],[24,25]],
                                    [[1,5],[8,12],[15,24],[25,26]]))


# ─────────────────────────────────────────────
# P08. Find Right Interval  [Medium][LC 436]
# ─────────────────────────────────────────────
"""
For each interval, find index of interval with smallest start >= current end.
Input: [[3,4],[2,3],[1,2]]  Output: [-1,0,1]
Strategy: sort starts, binary search for each end.
"""
import bisect

def findRightInterval(intervals: List[List[int]]) -> List[int]:
    # Map start → original index
    start_map = sorted((s, i) for i, (s, e) in enumerate(intervals))
    starts = [s for s, _ in start_map]

    result = []
    for start, end in intervals:
        pos = bisect.bisect_left(starts, end)
        if pos < len(starts):
            result.append(start_map[pos][1])
        else:
            result.append(-1)
    return result

print("P08:", findRightInterval([[3,4],[2,3],[1,2]]))  # [-1,0,1]


# ─────────────────────────────────────────────
# P09. Remove Covered Intervals  [Medium][LC 1288]
# ─────────────────────────────────────────────
"""
Remove interval if it's covered by another interval.
[a,b] covered by [c,d] if c<=a and b<=d.
Input: [[1,4],[3,6],[2,8]]  Output: 2 (remove [1,4] covered by [2,8])
Strategy: sort by start ASC, then by end DESC (longer intervals first at same start).
Track max_end: if current end <= max_end → covered.
"""
def removeCoveredIntervals(intervals: List[List[int]]) -> int:
    intervals.sort(key=lambda x: (x[0], -x[1]))  # start ASC, end DESC
    count = 0
    max_end = 0
    for start, end in intervals:
        if end > max_end:
            count += 1
            max_end = end
        # else: covered by previous interval with same/smaller start and larger end
    return count

print("P09:", removeCoveredIntervals([[1,4],[3,6],[2,8]]))   # 2
print("P09:", removeCoveredIntervals([[1,2],[1,4],[3,4]]))   # 1


# ─────────────────────────────────────────────
# P10. Count Days Without Meetings  [Medium][LC 3169]
# ─────────────────────────────────────────────
"""
Total days = days. meetings = list of [start, end] (1-indexed).
Count days with no meetings.
Input: days=10, meetings=[[5,7],[1,3],[9,10]]  Output: 2 (days 4 and 8)
Strategy: merge meetings, count gaps.
"""
def countDays(days: int, meetings: List[List[int]]) -> int:
    meetings.sort()
    merged = [meetings[0][:]]
    for s, e in meetings[1:]:
        if s <= merged[-1][1] + 1:       # adjacent or overlapping
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])

    # Count days covered by merged meetings
    covered = sum(e - s + 1 for s, e in merged)
    return days - covered

print("P10:", countDays(10, [[5,7],[1,3],[9,10]]))  # 2
print("P10:", countDays(5,  [[2,4],[1,3]]))         # 1


"""
COMPLEXITY SUMMARY:
─────────────────────────────────────────────────────────────
Merge Intervals          O(n log n) O(n)  sort by start + scan
Insert Interval          O(n)       O(n)  3-phase linear scan
Meeting Rooms I          O(n log n) O(1)  sort + adjacent check
Meeting Rooms II         O(n log n) O(n)  min-heap of end times
Non-overlapping (erase)  O(n log n) O(1)  greedy sort-by-end
Min Arrows               O(n log n) O(1)  greedy sort-by-end
Interval Intersections   O(n+m)     O(1)  two pointers
Find Right Interval      O(n log n) O(n)  sorted starts + bisect
Remove Covered           O(n log n) O(1)  sort start-ASC end-DESC
Count Free Days          O(n log n) O(n)  merge + count gaps
"""
