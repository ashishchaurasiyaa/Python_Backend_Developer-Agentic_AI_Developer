"""
╔══════════════════════════════════════════════════════════════════╗
║         HEAPS & PRIORITY QUEUES — 18 LeetCode-Style Problems     ║
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

print("\n✓ All 18 Heap & Priority Queue problems solved!")

# ══════════════════════════════════════════════════════════════════
# Problem 11: Design Twitter (LC 355)
# ══════════════════════════════════════════════════════════════════
class Twitter:
    """
    Design a simplified Twitter:
      - postTweet(userId, tweetId): compose a new tweet.
      - getNewsFeed(userId): 10 most recent tweet ids from the user and
        everyone they follow (most recent first).
      - follow(followerId, followeeId) / unfollow(followerId, followeeId).

    Approach: Store each user's tweets as (time, tweetId) in a list
    (already chronological since posts append). To build the feed,
    push the most recent tweet of each relevant user onto a max heap
    (negate time), pop the global max repeatedly, and push that
    user's next-most-recent tweet — classic "merge k sorted lists".

    Example:
      twitter = Twitter()
      twitter.postTweet(1, 5)
      twitter.getNewsFeed(1)       -> [5]
      twitter.follow(1, 2)
      twitter.postTweet(2, 6)
      twitter.getNewsFeed(1)       -> [6, 5]
      twitter.unfollow(1, 2)
      twitter.getNewsFeed(1)       -> [5]
    """
    def __init__(self):
        self.timer = 0
        self.tweets = defaultdict(list)     # userId -> [(time, tweetId), ...]
        self.followees = defaultdict(set)   # userId -> set of followeeIds

    def postTweet(self, userId: int, tweetId: int) -> None:
        self.tweets[userId].append((self.timer, tweetId))
        self.timer += 1

    def getNewsFeed(self, userId: int) -> List[int]:
        heap = []
        users = self.followees[userId] | {userId}
        for u in users:
            tweets = self.tweets[u]
            if tweets:
                i = len(tweets) - 1
                time, tweetId = tweets[i]
                heapq.heappush(heap, (-time, tweetId, u, i - 1))

        result = []
        while heap and len(result) < 10:
            neg_time, tweetId, u, i = heapq.heappop(heap)
            result.append(tweetId)
            if i >= 0:
                time, tid = self.tweets[u][i]
                heapq.heappush(heap, (-time, tid, u, i - 1))
        return result

    def follow(self, followerId: int, followeeId: int) -> None:
        if followerId != followeeId:
            self.followees[followerId].add(followeeId)

    def unfollow(self, followerId: int, followeeId: int) -> None:
        self.followees[followerId].discard(followeeId)

print("\n=== Design Twitter ===")
twitter = Twitter()
twitter.postTweet(1, 5)
print(twitter.getNewsFeed(1))   # [5]
twitter.follow(1, 2)
twitter.postTweet(2, 6)
print(twitter.getNewsFeed(1))   # [6, 5]
twitter.unfollow(1, 2)
print(twitter.getNewsFeed(1))   # [5]
# Time: O(n log n) per feed (n = followees) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 12: Design Hit Counter (LC 362)
# ══════════════════════════════════════════════════════════════════
from collections import deque

class HitCounter:
    """
    Design a hit counter that counts hits received in the past 300 seconds.
      - hit(timestamp): record a hit at timestamp (calls are non-decreasing).
      - getHits(timestamp): return number of hits in [timestamp-300, timestamp].

    Approach: Queue-based sliding window. Hits are appended in order
    (timestamps only increase), so the oldest hit is always at the front.
    On getHits, evict everything older than 300s from the front, then
    the remaining queue length is the answer.

    Example:
      counter = HitCounter()
      counter.hit(1); counter.hit(2); counter.hit(3)
      counter.getHits(4)   -> 3
      counter.hit(300)
      counter.getHits(300) -> 4
      counter.getHits(301) -> 3
    """
    def __init__(self):
        self.hits = deque()  # timestamps, oldest first

    def hit(self, timestamp: int) -> None:
        self.hits.append(timestamp)

    def getHits(self, timestamp: int) -> int:
        while self.hits and self.hits[0] <= timestamp - 300:
            self.hits.popleft()
        return len(self.hits)

print("\n=== Design Hit Counter ===")
counter = HitCounter()
counter.hit(1)
counter.hit(2)
counter.hit(3)
print(counter.getHits(4))    # 3
counter.hit(300)
print(counter.getHits(300))  # 4
print(counter.getHits(301))  # 3
# Time: O(1) amortized per call | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 13: Smallest Range Covering Elements from K Lists (LC 632)
# ══════════════════════════════════════════════════════════════════
def smallestRange(nums: List[List[int]]) -> List[int]:
    """
    Given k sorted lists, find the smallest range [a, b] that includes
    at least one number from each of the k lists.

    Approach: Min heap seeded with the first element of every list
    (plus track the current max across the heap). Repeatedly pop the
    smallest, compare (current_max - smallest) to the best range found,
    then advance that list's pointer and push its next element,
    updating current_max. Stop when any list is exhausted (can't
    shrink further usefully once one list runs out).

    Example:
      [[4,10,15,24,26],[0,9,12,20],[5,18,22,30]] -> [20,24]
    """
    heap = []
    current_max = float('-inf')
    for i, lst in enumerate(nums):
        heapq.heappush(heap, (lst[0], i, 0))
        current_max = max(current_max, lst[0])

    best_range = [float('-inf'), float('inf')]

    while True:
        val, i, j = heapq.heappop(heap)
        if current_max - val < best_range[1] - best_range[0]:
            best_range = [val, current_max]
        if j + 1 == len(nums[i]):
            break
        next_val = nums[i][j + 1]
        current_max = max(current_max, next_val)
        heapq.heappush(heap, (next_val, i, j + 1))

    return best_range

print("\n=== Smallest Range Covering Elements from K Lists ===")
print(smallestRange([[4,10,15,24,26],[0,9,12,20],[5,18,22,30]]))  # [20, 24]
# Time: O(n log k) | Space: O(k)

# ══════════════════════════════════════════════════════════════════
# Problem 14: Find K Closest Elements (LC 658)
# ══════════════════════════════════════════════════════════════════
def findClosestElements(arr: List[int], k: int, x: int) -> List[int]:
    """
    Given a sorted array arr and a target x, return the k closest
    elements to x, sorted in ascending order. On a distance tie,
    prefer the smaller value.

    Approach: Min heap keyed on (abs(value - x), value). Ties on
    distance naturally resolve to the smaller value first because
    the tuple comparison falls through to the value. Pop k times,
    then sort the result (heap pop order isn't ascending by value).

    Example:
      arr=[1,2,3,4,5], k=4, x=3    -> [1,2,3,4]
      arr=[1,1,2,3,4,5], k=4, x=-1 -> [1,1,2,3]
    """
    heap = []
    for num in arr:
        heapq.heappush(heap, (abs(num - x), num))

    closest = [heapq.heappop(heap)[1] for _ in range(k)]
    return sorted(closest)

print("\n=== Find K Closest Elements ===")
print(findClosestElements([1,2,3,4,5], 4, 3))     # [1, 2, 3, 4]
print(findClosestElements([1,1,2,3,4,5], 4, -1))  # [1, 1, 2, 3]
# Time: O(n log n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 15: Employee Free Time (LC 759)
# ══════════════════════════════════════════════════════════════════
class Interval:
    def __init__(self, start=0, end=0):
        self.start = start
        self.end = end
    def __repr__(self):
        return f"[{self.start},{self.end}]"
    def __eq__(self, other):
        return isinstance(other, Interval) and self.start == other.start and self.end == other.end

def employeeFreeTime(schedule: List[List['Interval']]) -> List['Interval']:
    """
    Given a list of schedules (one sorted, non-overlapping list of
    Intervals per employee), find the common free time across ALL
    employees, represented as a sorted list of finite Intervals
    (ignore the unbounded time before the first and after the last).

    Approach: Merge-k-sorted-lists via a min heap keyed by interval
    start. Pop intervals in global start order while tracking the
    running "busy until" watermark (prev_end). Any gap between
    prev_end and the next popped interval's start is free time.

    Example:
      [[[1,2],[5,6]], [[1,3]], [[4,10]]] -> [[3,4]]
    """
    heap = []
    for i, emp in enumerate(schedule):
        if emp:
            heapq.heappush(heap, (emp[0].start, i, 0))

    result = []
    prev_end = None
    while heap:
        start, i, j = heapq.heappop(heap)
        interval = schedule[i][j]
        if prev_end is not None and start > prev_end:
            result.append(Interval(prev_end, start))
        prev_end = interval.end if prev_end is None else max(prev_end, interval.end)
        if j + 1 < len(schedule[i]):
            heapq.heappush(heap, (schedule[i][j + 1].start, i, j + 1))

    return result

print("\n=== Employee Free Time ===")
_schedule = [
    [Interval(1, 2), Interval(5, 6)],
    [Interval(1, 3)],
    [Interval(4, 10)],
]
print(employeeFreeTime(_schedule))  # [[3,4]]
# Time: O(n log k) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 16: Last Stone Weight (LC 1046)
# ══════════════════════════════════════════════════════════════════
def lastStoneWeight(stones: List[int]) -> int:
    """
    Repeatedly smash the two heaviest stones together: if equal weight,
    both are destroyed; otherwise the lighter is destroyed and the
    heavier becomes (heavy - light). Return the weight of the last
    remaining stone (0 if none remain).

    Approach: Max heap (negate weights). Pop the two heaviest, push
    back their difference if nonzero, repeat until <= 1 stone remains.

    Example:
      [2,7,4,1,8,1] -> 1
    """
    heap = [-s for s in stones]
    heapq.heapify(heap)

    while len(heap) > 1:
        y = -heapq.heappop(heap)
        x = -heapq.heappop(heap)
        if y != x:
            heapq.heappush(heap, -(y - x))

    return -heap[0] if heap else 0

print("\n=== Last Stone Weight ===")
print(lastStoneWeight([2,7,4,1,8,1]))  # 1
# Time: O(n log n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 17: Minimum Interval to Include Each Query (LC 1851)
# ══════════════════════════════════════════════════════════════════
def minInterval(intervals: List[List[int]], queries: List[int]) -> List[int]:
    """
    Given intervals [l, r] and queries (points), for each query return
    the size (r - l + 1) of the smallest interval that contains it,
    or -1 if none does.

    Approach: Offline. Sort intervals by start, sort queries ascending
    (keeping original indices conceptually via a result dict). Sweep
    queries left to right; push every interval whose start <= query
    onto a min heap keyed by (size, end). Pop stale intervals whose
    end < query (they can't cover this or any later query). The heap
    top is then the smallest interval covering the current query.

    Example:
      intervals=[[1,4],[2,4],[3,6],[4,4]], queries=[2,3,4,5] -> [3,3,1,4]
    """
    intervals = sorted(intervals)
    result = {}
    heap = []  # (size, end)
    i = 0
    n = len(intervals)

    for q in sorted(queries):
        while i < n and intervals[i][0] <= q:
            start, end = intervals[i]
            heapq.heappush(heap, (end - start + 1, end))
            i += 1
        while heap and heap[0][1] < q:
            heapq.heappop(heap)
        result[q] = heap[0][0] if heap else -1

    return [result[q] for q in queries]

print("\n=== Minimum Interval to Include Each Query ===")
print(minInterval([[1,4],[2,4],[3,6],[4,4]], [2,3,4,5]))  # [3, 3, 1, 4]
# Time: O((n + q) log n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 18: Detect Squares (LC 2013)
# ══════════════════════════════════════════════════════════════════
class DetectSquares:
    """
    Design a data structure that:
      - add(point): adds a point (duplicates allowed) to the stream.
      - count(point): counts axis-aligned squares that can be formed
        using this point as one corner and three previously added
        points as the other corners.

    Approach: Hashmap based (not a heap problem, included per the
    requested set). Store frequency per (x, y). For count(point),
    scan every stored point sharing the same x-coordinate (a
    potential vertical edge partner); its y-distance to the query
    point is a candidate square side length. For each of the two
    horizontal directions, multiply the frequencies of the three
    partner corners together and accumulate.

    Example:
      add([3,10]); add([11,2]); add([3,2])
      count([11,10]) -> 1
      add([3,2])
      count([11,10]) -> 2
    """
    def __init__(self):
        self.point_count = defaultdict(int)

    def add(self, point: List[int]) -> None:
        x, y = point
        self.point_count[(x, y)] += 1

    def count(self, point: List[int]) -> int:
        x, y = point
        total = 0
        for (px, py), cnt in list(self.point_count.items()):
            if px != x or py == y:
                continue
            side = py - y
            for x2 in (x + side, x - side):
                total += cnt * self.point_count.get((x2, y), 0) * self.point_count.get((x2, py), 0)
        return total

print("\n=== Detect Squares ===")
ds = DetectSquares()
ds.add([3, 10])
ds.add([11, 2])
ds.add([3, 2])
print(ds.count([11, 10]))  # 1
ds.add([3, 2])
print(ds.count([11, 10]))  # 2
# Time: O(n) per count (n = distinct points sharing x) | Space: O(n)

print("\n✓ All 8 additional problems (P11-P18) solved!")
