"""
╔══════════════════════════════════════════════════════════════════╗
║         HEAPS & PRIORITY QUEUES — 10 LeetCode-Style Problems     ║
╚══════════════════════════════════════════════════════════════════╝
"""

from typing import List, Optional
import heapq
from collections import Counter, defaultdict

# ══════════════════════════════════════════════════════════════════
# Problem 1: Kth Largest Element in an Array (LC 215)
# ══════════════════════════════════════════════════════════════════
def findKthLargest(nums: List[int], k: int) -> int:
    """
    Find the kth largest element in an unsorted array.

    Approach: Maintain a min heap of size k. The top is always the kth largest.
    Push each element. If size > k, pop the minimum.

    Example:
      [3,2,1,5,6,4], k=2 → 5
      [3,2,3,1,2,4,5,5,6], k=4 → 4
    """
    heap = []
    for num in nums:
        heapq.heappush(heap, num)
        if len(heap) > k:
            heapq.heappop(heap)
    return heap[0]

print("=== Kth Largest Element ===")
print(findKthLargest([3,2,1,5,6,4], 2))       # 5
print(findKthLargest([3,2,3,1,2,4,5,5,6], 4)) # 4
# Time: O(n log k) | Space: O(k)

# ══════════════════════════════════════════════════════════════════
# Problem 2: K Closest Points to Origin (LC 973)
# ══════════════════════════════════════════════════════════════════
def kClosest(points: List[List[int]], k: int) -> List[List[int]]:
    """
    Return the k closest points to the origin (0,0).
    Distance² = x² + y² (no need for sqrt).

    Approach: Max heap of size k on negative distance (negate for max).
    Keep k closest → those with smallest distance.

    Example:
      [[1,3],[-2,2]], k=1 → [[-2,2]]
      [[3,3],[5,-1],[-2,4]], k=2 → [[3,3],[-2,4]]
    """
    heap = []
    for x, y in points:
        dist_sq = x*x + y*y
        heapq.heappush(heap, (-dist_sq, x, y))
        if len(heap) > k:
            heapq.heappop(heap)
    return [[x, y] for _, x, y in heap]

print("\n=== K Closest Points to Origin ===")
print(kClosest([[1,3],[-2,2]], 1))          # [[-2,2]]
print(kClosest([[3,3],[5,-1],[-2,4]], 2))   # [[3,3],[-2,4]]
# Time: O(n log k) | Space: O(k)

# ══════════════════════════════════════════════════════════════════
# Problem 3: Task Scheduler (LC 621)
# ══════════════════════════════════════════════════════════════════
def leastInterval(tasks: List[str], n: int) -> int:
    """
    Execute all tasks with cooldown n (same task must wait n units).
    Return minimum number of intervals needed.

    Approach: Max heap (by frequency) + cooldown queue.
    Each time unit: run the most frequent available task.
    If a task becomes available (cooldown expired), re-add to heap.

    Example:
      tasks=["A","A","A","B","B","B"], n=2 → 8
      tasks=["A","A","A","B","B","B"], n=0 → 6
    """
    count = Counter(tasks)
    max_heap = [-c for c in count.values()]
    heapq.heapify(max_heap)
    queue = []  # (neg_count, available_time)
    time = 0

    while max_heap or queue:
        time += 1
        if max_heap:
            cnt = 1 + heapq.heappop(max_heap)  # execute once (decrement)
            if cnt < 0:
                queue.append((cnt, time + n))
        # Check if any cooled-down task is ready
        if queue and queue[0][1] == time:
            heapq.heappush(max_heap, heapq.heappop(queue)[0])

    return time

print("\n=== Task Scheduler ===")
print(leastInterval(["A","A","A","B","B","B"], 2))  # 8
print(leastInterval(["A","A","A","B","B","B"], 0))  # 6
# Time: O(n log n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 4: Find Median from Data Stream (LC 295)
# ══════════════════════════════════════════════════════════════════
class MedianFinder:
    """
    Support two operations:
    - addNum(num): add a number to the data structure
    - findMedian(): return the median of all numbers added so far

    Approach: Two heaps.
    max_heap (negated): left half (smaller values)
    min_heap: right half (larger values)
    Invariant: max_heap.size == min_heap.size or +1.

    Example:
      addNum(1), addNum(2), findMedian() → 1.5
      addNum(3), findMedian() → 2.0
    """
    def __init__(self):
        self.max_heap = []  # left half, negated
        self.min_heap = []  # right half

    def addNum(self, num: int) -> None:
        heapq.heappush(self.max_heap, -num)
        # Ensure all left <= all right
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
        return (-self.max_heap[0] + self.min_heap[0]) / 2.0

print("\n=== Find Median from Data Stream ===")
mf = MedianFinder()
mf.addNum(1); mf.addNum(2)
print(mf.findMedian())  # 1.5
mf.addNum(3)
print(mf.findMedian())  # 2.0
# Time: O(log n) addNum, O(1) findMedian | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 5: Top K Frequent Words (LC 692)
# ══════════════════════════════════════════════════════════════════
def topKFrequent(words: List[str], k: int) -> List[str]:
    """
    Return the k most frequent words. Ties broken alphabetically.

    Approach: Use a min heap of size k with (-freq, word) tuples.
    Python sorts tuples lexicographically, so (-freq, word) gives
    correct priority: higher freq first, then alphabetical for ties.

    Example:
      ["i","love","leetcode","i","love","coding"], k=2 → ["i","love"]
      ["the","day","is","sunny","the","the","the","sunny","is","is"], k=4
        → ["the","is","sunny","day"]
    """
    count = Counter(words)
    heap = []
    for word, freq in count.items():
        heapq.heappush(heap, (-freq, word))

    return [heapq.heappop(heap)[1] for _ in range(k)]

print("\n=== Top K Frequent Words ===")
print(topKFrequent(["i","love","leetcode","i","love","coding"], 2))  # ["i","love"]
print(topKFrequent(["the","day","is","sunny","the","the","the","sunny","is","is"], 4))
# ["the","is","sunny","day"]
# Time: O(n log k) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 6: Merge K Sorted Lists (LC 23) — Heap Approach
# ══════════════════════════════════════════════════════════════════
class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next
    def __lt__(self, other):
        return self.val < other.val  # needed for heap comparison

def mergeKLists(lists: List[Optional[ListNode]]) -> Optional[ListNode]:
    """
    Merge k sorted linked lists into one sorted list.

    Approach: Min heap with (node.val, node). Initialize with head of each list.
    Pop min, add to result, push its next node.

    Example:
      [[1,4,5],[1,3,4],[2,6]] → [1,1,2,3,4,4,5,6]
    """
    heap = []
    for node in lists:
        if node:
            heapq.heappush(heap, node)

    dummy = ListNode(0)
    curr = dummy
    while heap:
        node = heapq.heappop(heap)
        curr.next = node
        curr = curr.next
        if node.next:
            heapq.heappush(heap, node.next)

    return dummy.next

def arr_to_ll(arr):
    dummy = ListNode(0); curr = dummy
    for x in arr: curr.next = ListNode(x); curr = curr.next
    return dummy.next

def ll_to_arr(head):
    result = []
    while head: result.append(head.val); head = head.next
    return result

print("\n=== Merge K Sorted Lists ===")
lists = [arr_to_ll([1,4,5]), arr_to_ll([1,3,4]), arr_to_ll([2,6])]
print(ll_to_arr(mergeKLists(lists)))  # [1,1,2,3,4,4,5,6]
# Time: O(n log k) | Space: O(k)

# ══════════════════════════════════════════════════════════════════
# Problem 7: Reorganize String (LC 767)
# ══════════════════════════════════════════════════════════════════
def reorganizeString(s: str) -> str:
    """
    Rearrange characters so no two adjacent characters are the same.
    Return "" if impossible.

    Approach: Max heap by frequency. Greedily place the most frequent
    character. Alternate: place most frequent, then second most frequent.
    Keep track of previous character and its count.

    Example:
      "aab" → "aba"
      "aaab" → ""
    """
    count = Counter(s)
    max_heap = [(-freq, char) for char, freq in count.items()]
    heapq.heapify(max_heap)

    result = []
    prev_freq, prev_char = 0, ''

    while max_heap:
        freq, char = heapq.heappop(max_heap)
        result.append(char)
        # Re-add previous character if it still has remaining count
        if prev_freq < 0:
            heapq.heappush(max_heap, (prev_freq, prev_char))
        prev_freq, prev_char = freq + 1, char  # freq+1 because freq is negative

    result_str = ''.join(result)
    return result_str if len(result_str) == len(s) else ""

print("\n=== Reorganize String ===")
print(reorganizeString("aab"))   # "aba"
print(reorganizeString("aaab"))  # ""
print(reorganizeString("vvvlo")) # "vlvov" or similar
# Time: O(n log n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 8: Find K Pairs with Smallest Sums (LC 373)
# ══════════════════════════════════════════════════════════════════
def kSmallestPairs(nums1: List[int], nums2: List[int], k: int) -> List[List[int]]:
    """
    Find k pairs (u,v) with smallest sums where u ∈ nums1, v ∈ nums2.

    Approach: Start with (nums1[i], nums2[0]) for all i.
    Use min heap. When we pop (nums1[i], nums2[j]), push (nums1[i], nums2[j+1]).
    Only initialize with first k pairs from nums1 (or all if < k).

    Example:
      nums1=[1,7,11], nums2=[2,4,6], k=3 → [[1,2],[1,4],[1,6]]
      nums1=[1,1,2], nums2=[1,2,3], k=2 → [[1,1],[1,1]]
    """
    if not nums1 or not nums2:
        return []

    result = []
    # (sum, i, j) — start with all pairs (nums1[i], nums2[0])
    heap = [(nums1[i] + nums2[0], i, 0) for i in range(min(k, len(nums1)))]
    heapq.heapify(heap)

    while heap and len(result) < k:
        s, i, j = heapq.heappop(heap)
        result.append([nums1[i], nums2[j]])
        if j + 1 < len(nums2):
            heapq.heappush(heap, (nums1[i] + nums2[j+1], i, j+1))

    return result

print("\n=== Find K Pairs with Smallest Sums ===")
print(kSmallestPairs([1,7,11], [2,4,6], 3))  # [[1,2],[1,4],[1,6]]
print(kSmallestPairs([1,1,2], [1,2,3], 2))   # [[1,1],[1,1]]
# Time: O(k log k) | Space: O(k)

# ══════════════════════════════════════════════════════════════════
# Problem 9: Sliding Window Median (LC 480)
# ══════════════════════════════════════════════════════════════════
def medianSlidingWindow(nums: List[int], k: int) -> List[float]:
    """
    Return the median of each sliding window of size k.

    Approach: Two heaps (max for left, min for right) + lazy deletion.
    Maintain the invariant for each window. When window slides,
    mark the outgoing element for lazy deletion.

    Example:
      nums=[1,3,-1,-3,5,3,6,7], k=3 → [1.0,-1.0,-1.0,3.0,5.0,6.0]
    """
    max_heap = []  # left half (negated)
    min_heap = []  # right half
    to_remove = defaultdict(int)
    result = []

    def add(num):
        heapq.heappush(max_heap, -num)
        heapq.heappush(min_heap, -heapq.heappop(max_heap))
        if len(min_heap) > len(max_heap):
            heapq.heappush(max_heap, -heapq.heappop(min_heap))

    def remove(num):
        to_remove[num] += 1
        # Lazy deletion: clean top if marked
        if num <= -max_heap[0]:
            # It's in max_heap side
            while max_heap and to_remove[-max_heap[0]] > 0:
                to_remove[-max_heap[0]] -= 1
                heapq.heappop(max_heap)
        else:
            while min_heap and to_remove[min_heap[0]] > 0:
                to_remove[min_heap[0]] -= 1
                heapq.heappop(min_heap)

    def get_median():
        if k % 2 == 1:
            return float(-max_heap[0])
        return (-max_heap[0] + min_heap[0]) / 2.0

    # Initialize first window
    for i in range(k):
        add(nums[i])

    result.append(get_median())

    for i in range(k, len(nums)):
        add(nums[i])
        remove(nums[i - k])
        # Clean up lazy deletions from tops
        while max_heap and to_remove[-max_heap[0]] > 0:
            to_remove[-max_heap[0]] -= 1
            heapq.heappop(max_heap)
        while min_heap and to_remove[min_heap[0]] > 0:
            to_remove[min_heap[0]] -= 1
            heapq.heappop(min_heap)
        # Rebalance
        while len(min_heap) > len(max_heap):
            heapq.heappush(max_heap, -heapq.heappop(min_heap))
        while len(max_heap) > len(min_heap) + 1:
            heapq.heappush(min_heap, -heapq.heappop(max_heap))
        result.append(get_median())

    return result

print("\n=== Sliding Window Median ===")
print(medianSlidingWindow([1,3,-1,-3,5,3,6,7], 3))  # [1.0,-1.0,-1.0,3.0,5.0,6.0]
# Time: O(n log k) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 10: IPO (LC 502)
# ══════════════════════════════════════════════════════════════════
def findMaximizedCapital(k: int, w: int, profits: List[int], capital: List[int]) -> int:
    """
    Given k projects to pick, initial capital w. Each project[i] requires
    capital[i] and yields profits[i]. Maximize final capital.

    Approach: Greedy with two heaps.
    1. Sort projects by required capital.
    2. Among all affordable projects, pick the most profitable one.
    Use a min heap (capital) for available projects sorting,
    and a max heap (profit) for selecting the best affordable project.

    Example:
      k=2, w=0, profits=[1,2,3], capital=[0,1,1] → 4
      k=3, w=0, profits=[1,2,3], capital=[0,1,2] → 6
    """
    projects = sorted(zip(capital, profits))  # sort by capital needed
    available = []  # max heap (negate profits)
    ptr = 0
    n = len(profits)

    for _ in range(k):
        # Add all projects we can afford
        while ptr < n and projects[ptr][0] <= w:
            heapq.heappush(available, -projects[ptr][1])
            ptr += 1
        if not available:
            break  # can't afford any project
        w += -heapq.heappop(available)  # pick most profitable

    return w

print("\n=== IPO ===")
print(findMaximizedCapital(2, 0, [1,2,3], [0,1,1]))  # 4
print(findMaximizedCapital(3, 0, [1,2,3], [0,1,2]))  # 6
# Time: O(n log n) | Space: O(n)

print("\n✓ All 10 Heap & Priority Queue problems solved!")
