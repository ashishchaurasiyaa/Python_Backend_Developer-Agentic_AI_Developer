"""
╔══════════════════════════════════════════════════════════════════╗
║           HEAPS & PRIORITY QUEUES — Complete Theory Guide        ║
╚══════════════════════════════════════════════════════════════════╝

WHAT IS A HEAP?
────────────────
A heap is a complete binary tree stored as an array where every parent
satisfies the heap property:
  Min-Heap: parent.val <= children.val  (root = minimum)
  Max-Heap: parent.val >= children.val  (root = maximum)

ARRAY REPRESENTATION:
  Parent of i   = (i - 1) // 2
  Left child    = 2*i + 1
  Right child   = 2*i + 2

PYTHON's heapq MODULE:
  Python only provides MIN HEAP via heapq.
  For max heap: negate the values (store -x, return -result).

COMPLEXITY TABLE
─────────────────────────────────────────────────────────────────
Operation          Time          Space
─────────────────────────────────────────────────────────────────
heappush(h, x)     O(log n)      —
heappop(h)         O(log n)      —
h[0] (peek min)    O(1)          —
heapify(list)      O(n)          O(1) extra
nlargest(k, it)    O(n log k)    O(k)
nsmallest(k, it)   O(n log k)    O(k)
─────────────────────────────────────────────────────────────────
"""

import heapq
from typing import List
from collections import Counter

# ─────────────────────────────────────────────
# 1. heapq MODULE BASICS
# ─────────────────────────────────────────────
print("=" * 60)
print("1. heapq MODULE — Min Heap")
print("=" * 60)

# Create a min heap
h = []
heapq.heappush(h, 5)
heapq.heappush(h, 1)
heapq.heappush(h, 3)
heapq.heappush(h, 2)

print(f"Heap: {h}")               # internal array representation
print(f"Peek min: {h[0]}")        # O(1)
print(f"Pop min: {heapq.heappop(h)}")  # 1
print(f"Pop min: {heapq.heappop(h)}")  # 2

# heapify — convert list to heap in O(n)
nums = [5, 3, 8, 1, 4, 2, 7]
heapq.heapify(nums)
print(f"\nAfter heapify: {nums}")
print(f"nsmallest(3): {heapq.nsmallest(3, [5,3,8,1,4,2,7])}")  # [1,2,3]
print(f"nlargest(3):  {heapq.nlargest(3, [5,3,8,1,4,2,7])}")   # [8,7,5]

# ─────────────────────────────────────────────
# 2. MAX HEAP — Negate Values
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("2. MAX HEAP using negation")
print("=" * 60)

max_heap = []
for val in [5, 1, 3, 2, 4]:
    heapq.heappush(max_heap, -val)

print(f"Max heap (negated): {max_heap}")
print(f"Peek max: {-max_heap[0]}")         # 5
print(f"Pop max: {-heapq.heappop(max_heap)}")  # 5
print(f"Pop max: {-heapq.heappop(max_heap)}")  # 4

# ─────────────────────────────────────────────
# 3. HEAP WITH TUPLES (Priority + Value)
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("3. HEAP WITH TUPLES (priority, value)")
print("=" * 60)

"""
Python compares tuples lexicographically.
(priority, value) → lowest priority number = highest priority.
Useful for Dijkstra, task scheduling.
"""
task_heap = []
heapq.heappush(task_heap, (3, "low priority task"))
heapq.heappush(task_heap, (1, "urgent task"))
heapq.heappush(task_heap, (2, "medium task"))

while task_heap:
    priority, task = heapq.heappop(task_heap)
    print(f"  Priority {priority}: {task}")

# ─────────────────────────────────────────────
# 4. PATTERN: TOP-K ELEMENTS
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("4. PATTERN: Top-K Elements")
print("=" * 60)

"""
FIND K LARGEST ELEMENTS:
  Use a MIN heap of size k.
  Push each element. If heap size > k, pop the minimum.
  Result: k largest elements remain.
  Time: O(n log k) — much better than O(n log n) sort when k << n.

FIND K SMALLEST ELEMENTS:
  Use a MAX heap of size k (negate values).
"""

def top_k_largest(nums: List[int], k: int) -> List[int]:
    """Return k largest elements using a min heap of size k."""
    heap = []
    for num in nums:
        heapq.heappush(heap, num)
        if len(heap) > k:
            heapq.heappop(heap)  # remove smallest
    return sorted(heap, reverse=True)

print(f"Top 3 of [3,1,4,1,5,9,2,6]: {top_k_largest([3,1,4,1,5,9,2,6], 3)}")
# [9, 6, 5]

# ─────────────────────────────────────────────
# 5. PATTERN: K-WAY MERGE
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("5. PATTERN: K-Way Merge (Merge K Sorted Lists)")
print("=" * 60)

"""
K-Way Merge: merge k sorted arrays/lists efficiently.
Use a min heap with (value, list_index, element_index).
Each pop gives the global minimum. Push the next element from that list.
Time: O(n log k) where n = total elements, k = number of lists.
"""

def merge_k_sorted(lists: List[List[int]]) -> List[int]:
    result = []
    heap = []
    # Initialize with first element of each list
    for i, lst in enumerate(lists):
        if lst:
            heapq.heappush(heap, (lst[0], i, 0))  # (val, list_idx, elem_idx)

    while heap:
        val, i, j = heapq.heappop(heap)
        result.append(val)
        if j + 1 < len(lists[i]):
            heapq.heappush(heap, (lists[i][j+1], i, j+1))

    return result

lists = [[1,4,7], [2,5,8], [3,6,9]]
print(f"Merged: {merge_k_sorted(lists)}")  # [1,2,3,4,5,6,7,8,9]

# ─────────────────────────────────────────────
# 6. PATTERN: MEDIAN STREAM
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("6. PATTERN: Median from Data Stream")
print("=" * 60)

"""
Two heaps approach:
  max_heap (left half): stores smaller half, negated for max behavior
  min_heap (right half): stores larger half

Invariant:
  max_heap always has elements <= min_heap
  len(max_heap) == len(min_heap) OR len(max_heap) == len(min_heap) + 1

Median:
  If equal sizes: avg of both tops
  If max_heap larger: max_heap top
"""

class MedianFinder:
    def __init__(self):
        self.max_heap = []  # left half (negated)
        self.min_heap = []  # right half

    def addNum(self, num: int) -> None:
        heapq.heappush(self.max_heap, -num)
        # Balance: ensure max_heap top <= min_heap top
        if self.min_heap and (-self.max_heap[0]) > self.min_heap[0]:
            heapq.heappush(self.min_heap, -heapq.heappop(self.max_heap))
        # Balance sizes
        if len(self.max_heap) > len(self.min_heap) + 1:
            heapq.heappush(self.min_heap, -heapq.heappop(self.max_heap))
        elif len(self.min_heap) > len(self.max_heap):
            heapq.heappush(self.max_heap, -heapq.heappop(self.min_heap))

    def findMedian(self) -> float:
        if len(self.max_heap) > len(self.min_heap):
            return float(-self.max_heap[0])
        return (-self.max_heap[0] + self.min_heap[0]) / 2

mf = MedianFinder()
for num in [1, 2, 3, 4, 5]:
    mf.addNum(num)
    print(f"  Added {num}, median = {mf.findMedian()}")

# ─────────────────────────────────────────────
# 7. PATTERN: HEAP FOR GREEDY SCHEDULING
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("7. PATTERN: Task Scheduling with Heap")
print("=" * 60)

"""
Task Scheduler (LC 621):
Given tasks with frequencies, schedule with cooldown n.
Use max heap to always execute the most frequent remaining task.
When cooling down, use a queue of (task, available_at_time).
"""

def leastInterval(tasks: List[str], n: int) -> int:
    count = Counter(tasks)
    max_heap = [-c for c in count.values()]
    heapq.heapify(max_heap)
    queue = []  # (neg_count, available_time)
    time = 0

    while max_heap or queue:
        time += 1
        if max_heap:
            cnt = 1 + heapq.heappop(max_heap)  # decrement count
            if cnt < 0:
                queue.append((cnt, time + n))  # cooldown until time+n
        if queue and queue[0][1] == time:
            heapq.heappush(max_heap, queue.pop(0)[0])

    return time

print(f"Task intervals for ['A','A','A','B','B','B'], n=2: {leastInterval(['A','A','A','B','B','B'], 2)}")  # 8

# ─────────────────────────────────────────────
# 8. INTERVIEW Q&A
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("INTERVIEW Q&A")
print("=" * 60)

qa = """
Q1: Why does Python only have a min heap?
A1: Design choice. For max heap, negate values: push -x, return -heap[0].
    For custom ordering, use negative or wrap in a class with __lt__.

Q2: When would you use a heap over sorting?
A2: When you don't need ALL elements sorted — just the top-K.
    Heap gives O(n log k) vs O(n log n) for full sort.
    Also for streaming data (online algorithm) where sort isn't possible.

Q3: What is the time complexity of building a heap from a list?
A3: O(n) using heapify — NOT O(n log n). This is because nodes near
    the bottom of the heap (the majority) take O(1) to sift down.
    Summing the work: n/2 * O(1) + n/4 * O(log 2) + ... = O(n).

Q4: When does a heap NOT guarantee sorted output?
A4: A heap only guarantees the root is min/max. Siblings within a level
    have no ordering relationship. To get sorted output, pop all: O(n log n).

Q5: How do you implement a priority queue where higher value = higher priority?
A5: Negate: heappush(h, -priority). heappop gives most negative = highest original.

Q6: What is the difference between heapreplace and heappushpop?
A6: heapreplace(h, x): pop then push x. Errors if heap is empty. Faster.
    heappushpop(h, x): push x then pop min. Works on empty heap.
    If x < h[0]: heappushpop returns x immediately without modifying h.
    If x >= h[0]: heapreplace is equivalent.

Q7: When to use two heaps (for median finding)?
A7: When you need to find the median of a stream. Split data at the median:
    max-heap for lower half, min-heap for upper half.
    Maintain size balance so median is always accessible in O(1).
"""
print(qa)
