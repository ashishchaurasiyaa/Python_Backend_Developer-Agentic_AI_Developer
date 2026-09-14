"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DSA — Heap/Priority Queue + Greedy Algorithms
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import heapq
from collections import Counter, defaultdict


# ─────────────────────────────────────────────────────────────────────────────
# HEAPQ MODULE PRIMER
# ─────────────────────────────────────────────────────────────────────────────
# Python's heapq is a MIN-HEAP by default.
# heapq.heappush(heap, item)   — O(log n)
# heapq.heappop(heap)          — O(log n), returns smallest
# heapq.heapify(list)          — O(n), convert list to heap in-place
# heap[0]                      — O(1) peek at minimum

# MIN-HEAP example:
min_heap = []
heapq.heappush(min_heap, 5)
heapq.heappush(min_heap, 1)
heapq.heappush(min_heap, 3)
print("Min-heap pop:", heapq.heappop(min_heap))   # 1

# MAX-HEAP trick — negate values:
max_heap = []
heapq.heappush(max_heap, -5)
heapq.heappush(max_heap, -1)
heapq.heappush(max_heap, -3)
print("Max-heap pop:", -heapq.heappop(max_heap))  # 5  (negate back)

# Heap with tuples — sorted by first element:
# heapq.heappush(heap, (priority, data))


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 1: HEAP PROBLEMS
# ═════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# 1a. KTH LARGEST ELEMENT IN AN ARRAY
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 215
# Time: O(n log k)   Space: O(k)

def findKthLargest(nums, k):
    """
    Find kth largest element (1-indexed).

    Strategy: maintain a min-heap of size k.
    - Push each element; if heap size > k, pop the smallest.
    - The root of the heap (smallest of top-k) is the kth largest.

    Why min-heap? We want to track the k largest values.
    The minimum of those k values = kth largest overall.
    """
    min_heap = []
    for num in nums:
        heapq.heappush(min_heap, num)
        if len(min_heap) > k:
            heapq.heappop(min_heap)
    return min_heap[0]


print("Kth Largest:", findKthLargest([3, 2, 1, 5, 6, 4], 2))    # 5
print("Kth Largest:", findKthLargest([3, 2, 3, 1, 2, 4, 5, 5, 6], 4))  # 4


# ─────────────────────────────────────────────────────────────────────────────
# 1b. TOP K FREQUENT ELEMENTS
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 347
# Time: O(n log k)   Space: O(n)

def topKFrequent(nums, k):
    """
    Return k most frequent elements.

    Strategy:
    1. Count frequencies with Counter.
    2. Use min-heap of size k keyed by frequency.
       (so least-frequent among top-k gets evicted)
    3. Return elements remaining in heap.

    Alternative: bucket sort O(n) — group by frequency.
    """
    count = Counter(nums)
    # min-heap of (frequency, element)
    heap = []
    for num, freq in count.items():
        heapq.heappush(heap, (freq, num))
        if len(heap) > k:
            heapq.heappop(heap)
    return [num for freq, num in heap]


print("Top K Frequent:", topKFrequent([1,1,1,2,2,3], 2))   # [1, 2]
print("Top K Frequent:", topKFrequent([1], 1))              # [1]


# ─────────────────────────────────────────────────────────────────────────────
# 1c. MERGE K SORTED LISTS
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 23
# Time: O(N log k) where N = total nodes, k = number of lists
# Space: O(k) for heap

class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

    def __lt__(self, other):
        return self.val < other.val   # needed for heap comparison


def mergeKLists(lists):
    """
    Merge k sorted linked lists into one sorted list.

    Strategy: min-heap with (value, node).
    1. Push head of each non-empty list into heap.
    2. Pop minimum, add to result, push its next node if exists.

    The heap always holds at most one node per list (size k).
    """
    heap = []
    for node in lists:
        if node:
            heapq.heappush(heap, (node.val, node))

    dummy = ListNode(0)
    curr = dummy

    while heap:
        val, node = heapq.heappop(heap)
        curr.next = node
        curr = curr.next
        if node.next:
            heapq.heappush(heap, (node.next.val, node.next))

    return dummy.next


# Test helper
def make_list(vals):
    dummy = ListNode(0)
    curr = dummy
    for v in vals:
        curr.next = ListNode(v)
        curr = curr.next
    return dummy.next

def list_to_arr(node):
    result = []
    while node:
        result.append(node.val)
        node = node.next
    return result

lists = [make_list([1,4,5]), make_list([1,3,4]), make_list([2,6])]
print("Merge K Lists:", list_to_arr(mergeKLists(lists)))  # [1,1,2,3,4,4,5,6]


# ─────────────────────────────────────────────────────────────────────────────
# 1d. TASK SCHEDULER
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 621
# Time: O(n log n)   Space: O(1) — at most 26 different tasks

def leastInterval(tasks, n):
    """
    Min time to execute all tasks with cooldown n between same tasks.
    At each time slot: execute most-frequent available task (greedy).

    Strategy: max-heap of (negative_count, task_char) + cooldown queue.
    - Pop most frequent task, execute it.
    - If cooldown > 0, push to cooldown_queue with release_time.
    - Advance time; release tasks whose cooldown has expired.
    """
    count = Counter(tasks)
    max_heap = [-cnt for cnt in count.values()]
    heapq.heapify(max_heap)

    time = 0
    cooldown_queue = []   # (release_time, neg_count)

    while max_heap or cooldown_queue:
        time += 1

        if max_heap:
            neg_cnt = heapq.heappop(max_heap)
            neg_cnt += 1   # use one instance (less negative = one less task)
            if neg_cnt < 0:
                cooldown_queue.append((time + n, neg_cnt))
        else:
            # CPU idle — jump to next available task
            time = cooldown_queue[0][0]

        # Release tasks whose cooldown has expired
        if cooldown_queue and cooldown_queue[0][0] <= time:
            _, neg_cnt = cooldown_queue.pop(0)
            heapq.heappush(max_heap, neg_cnt)

    return time


print("Task Scheduler:", leastInterval(["A","A","A","B","B","B"], 2))  # 8
print("Task Scheduler:", leastInterval(["A","A","A","B","B","B"], 0))  # 6


# ─────────────────────────────────────────────────────────────────────────────
# 1e. FIND MEDIAN FROM DATA STREAM (Two Heaps)
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 295
# addNum: O(log n)   findMedian: O(1)   Space: O(n)

class MedianFinder:
    """
    Maintain two heaps:
    - small: max-heap of lower half  (negate for Python min-heap)
    - large: min-heap of upper half

    Invariant:
    1. len(small) == len(large) OR len(small) == len(large) + 1
    2. max(small) <= min(large)  (all small elements <= all large elements)

    Median:
    - Even total: average of max(small) and min(large)
    - Odd total:  max(small)  (small always has the extra element)
    """
    def __init__(self):
        self.small = []   # max-heap (negated): lower half
        self.large = []   # min-heap: upper half

    def addNum(self, num):
        # Push to small (max-heap)
        heapq.heappush(self.small, -num)

        # Balance: ensure max(small) <= min(large)
        if self.small and self.large and (-self.small[0]) > self.large[0]:
            heapq.heappush(self.large, -heapq.heappop(self.small))

        # Rebalance sizes: small can have at most 1 more than large
        if len(self.small) > len(self.large) + 1:
            heapq.heappush(self.large, -heapq.heappop(self.small))
        if len(self.large) > len(self.small):
            heapq.heappush(self.small, -heapq.heappop(self.large))

    def findMedian(self):
        if len(self.small) > len(self.large):
            return float(-self.small[0])
        return (-self.small[0] + self.large[0]) / 2.0


mf = MedianFinder()
mf.addNum(1)
mf.addNum(2)
print("Median:", mf.findMedian())   # 1.5
mf.addNum(3)
print("Median:", mf.findMedian())   # 2.0


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 2: GREEDY ALGORITHMS
# ═════════════════════════════════════════════════════════════════════════════
# Greedy pattern: make locally optimal choice at each step,
# prove it leads to globally optimal solution.

# ─────────────────────────────────────────────────────────────────────────────
# 2a. MERGE INTERVALS
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 56
# Time: O(n log n)   Space: O(n)

def merge(intervals):
    """
    Merge all overlapping intervals.

    Greedy: sort by start time. For each interval:
    - If it overlaps with last merged interval (start <= last end), extend end.
    - Otherwise, add new interval to result.

    Two intervals [a,b] and [c,d] overlap iff c <= b.
    """
    if not intervals:
        return []

    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]

    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:                     # overlap
            merged[-1] = [last_start, max(last_end, end)]
        else:                                      # no overlap
            merged.append([start, end])

    return merged


print("Merge Intervals:", merge([[1,3],[2,6],[8,10],[15,18]]))  # [[1,6],[8,10],[15,18]]
print("Merge Intervals:", merge([[1,4],[4,5]]))                 # [[1,5]]


# ─────────────────────────────────────────────────────────────────────────────
# 2b. JUMP GAME I
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 55
# Time: O(n)   Space: O(1)

def canJump(nums):
    """
    Can you reach the last index? nums[i] = max jump length from i.

    Greedy: track the farthest reachable index.
    At each index i, if i > max_reach, we're stuck — return False.
    Otherwise update max_reach = max(max_reach, i + nums[i]).
    """
    max_reach = 0
    for i, jump in enumerate(nums):
        if i > max_reach:
            return False
        max_reach = max(max_reach, i + jump)
    return True


print("Can Jump:", canJump([2, 3, 1, 1, 4]))   # True
print("Can Jump:", canJump([3, 2, 1, 0, 4]))   # False


# ─────────────────────────────────────────────────────────────────────────────
# 2c. JUMP GAME II — Minimum Jumps
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 45
# Time: O(n)   Space: O(1)

def jump(nums):
    """
    Minimum number of jumps to reach last index (guaranteed reachable).

    Greedy BFS approach:
    - current_end: the farthest we can reach with 'jumps' number of jumps
    - farthest: the farthest we can reach from anywhere in current window

    When we exhaust the current window (i == current_end),
    we must take another jump — extend window to farthest.
    """
    jumps = 0
    current_end = 0
    farthest = 0

    for i in range(len(nums) - 1):   # don't need to jump from last index
        farthest = max(farthest, i + nums[i])
        if i == current_end:          # exhausted current jump range
            jumps += 1
            current_end = farthest
            if current_end >= len(nums) - 1:
                break

    return jumps


print("Jump Game II:", jump([2, 3, 1, 1, 4]))        # 2
print("Jump Game II:", jump([2, 3, 0, 1, 4]))        # 2
print("Jump Game II:", jump([1, 2, 1, 1, 1]))        # 3


# ─────────────────────────────────────────────────────────────────────────────
# 2d. MEETING ROOMS II — Minimum Conference Rooms
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 253
# Time: O(n log n)   Space: O(n)

def minMeetingRooms(intervals):
    """
    Minimum number of conference rooms required.

    Strategy: min-heap tracks end times of ongoing meetings.
    For each meeting (sorted by start):
    - If earliest ending meeting ends before this one starts: reuse that room.
    - Otherwise: open a new room.
    Heap size = current rooms in use; max seen = answer.
    """
    if not intervals:
        return 0

    intervals.sort(key=lambda x: x[0])
    heap = []   # min-heap of end times

    for start, end in intervals:
        if heap and heap[0] <= start:
            heapq.heapreplace(heap, end)   # reuse room: replace earliest end
        else:
            heapq.heappush(heap, end)      # new room needed

    return len(heap)


print("Meeting Rooms II:", minMeetingRooms([[0,30],[5,10],[15,20]]))   # 2
print("Meeting Rooms II:", minMeetingRooms([[7,10],[2,4]]))            # 1
print("Meeting Rooms II:", minMeetingRooms([[1,5],[2,6],[3,7]]))       # 3


# ─────────────────────────────────────────────────────────────────────────────
# 2e. GAS STATION
# ─────────────────────────────────────────────────────────────────────────────
# LeetCode 134
# Time: O(n)   Space: O(1)

def canCompleteCircuit(gas, cost):
    """
    Find starting gas station index for a complete circular trip.
    Returns -1 if impossible.

    Key observations:
    1. If total gas >= total cost, a solution ALWAYS exists.
    2. If we fail at station i, the starting point must be AFTER i.
       (Any station between current start and i would fail even earlier.)

    Greedy: try each station as starting point.
    Reset when tank goes negative; track the candidate start.
    """
    total_surplus = 0
    curr_surplus = 0
    start = 0

    for i in range(len(gas)):
        net = gas[i] - cost[i]
        total_surplus += net
        curr_surplus  += net

        if curr_surplus < 0:
            # Cannot reach from current start; try next station
            curr_surplus = 0
            start = i + 1

    return start if total_surplus >= 0 else -1


print("Gas Station:", canCompleteCircuit([1,2,3,4,5], [3,4,5,1,2]))  # 3
print("Gas Station:", canCompleteCircuit([2,3,4], [3,4,3]))           # -1


# ─────────────────────────────────────────────────────────────────────────────
# COMPLEXITY SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
"""
Problem                         Time            Space       Key Idea
────────────────────────────────────────────────────────────────────────────────
Kth Largest Element             O(n log k)      O(k)        Min-heap of size k
Top K Frequent                  O(n log k)      O(n)        Min-heap by frequency
Merge K Sorted Lists            O(N log k)      O(k)        Min-heap, k = lists
Task Scheduler                  O(n log n)      O(1)        Max-heap + cooldown queue
Find Median (Two Heaps)         O(log n) add    O(n)        Balanced max+min heaps
                                O(1) query
Merge Intervals                 O(n log n)      O(n)        Sort by start, extend end
Jump Game I                     O(n)            O(1)        Track max reachable index
Jump Game II                    O(n)            O(1)        Greedy BFS window
Meeting Rooms II                O(n log n)      O(n)        Min-heap of end times
Gas Station                     O(n)            O(1)        Reset start on deficit
────────────────────────────────────────────────────────────────────────────────
HEAP RULES:
  Min-heap  → heapq (default)
  Max-heap  → negate values before pushing, negate back when popping
  Tuple heap → sorted by first element; include index as tiebreaker if needed:
               heapq.heappush(heap, (priority, index, data))
"""
