"""
╔══════════════════════════════════════════════════════════════════╗
║           SORTING ALGORITHMS — 10 LeetCode-Style Problems        ║
╚══════════════════════════════════════════════════════════════════╝
"""

from typing import List, Optional
import heapq
from functools import cmp_to_key

# ══════════════════════════════════════════════════════════════════
# Problem 1: Sort Colors - Dutch National Flag (LC 75)
# ══════════════════════════════════════════════════════════════════
def sortColors(nums: List[int]) -> None:
    """
    Sort array of 0s, 1s, 2s in-place without using library sort.
    (Dutch National Flag problem by Dijkstra)

    Approach: Three pointers — lo (next 0 position), mid (current),
    hi (next 2 position). Single pass.
    - nums[mid] == 0: swap with lo, advance both
    - nums[mid] == 1: just advance mid
    - nums[mid] == 2: swap with hi, advance hi backward (don't advance mid)

    Example:
      [2,0,2,1,1,0] → [0,0,1,1,2,2]
    """
    lo, mid, hi = 0, 0, len(nums) - 1
    while mid <= hi:
        if nums[mid] == 0:
            nums[lo], nums[mid] = nums[mid], nums[lo]
            lo += 1; mid += 1
        elif nums[mid] == 1:
            mid += 1
        else:  # nums[mid] == 2
            nums[mid], nums[hi] = nums[hi], nums[mid]
            hi -= 1
            # Don't advance mid — newly swapped value needs checking

print("=== Sort Colors (Dutch Flag) ===")
nums = [2,0,2,1,1,0]
sortColors(nums)
print(nums)  # [0,0,1,1,2,2]
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 2: Kth Largest Element (LC 215) — QuickSelect
# ══════════════════════════════════════════════════════════════════
def findKthLargest(nums: List[int], k: int) -> int:
    """
    Find the kth largest element in an unsorted array.
    Do not sort the entire array.

    Approach: QuickSelect — partial Quick Sort.
    Partition around pivot. If pivot lands at position (n-k),
    we found it. Otherwise recurse on the relevant half.
    Average O(n), no extra space.

    Example:
      [3,2,1,5,6,4], k=2 → 5
      [3,2,3,1,2,4,5,5,6], k=4 → 4
    """
    import random

    def quickselect(lo, hi, target_idx):
        pivot = nums[hi]
        store = lo
        for j in range(lo, hi):
            if nums[j] <= pivot:
                nums[store], nums[j] = nums[j], nums[store]
                store += 1
        nums[store], nums[hi] = nums[hi], nums[store]

        if store == target_idx:
            return nums[store]
        elif store < target_idx:
            return quickselect(store + 1, hi, target_idx)
        else:
            return quickselect(lo, store - 1, target_idx)

    # kth largest = element at index (n - k) in 0-indexed sorted order
    n = len(nums)
    # Shuffle for guaranteed average performance
    random.shuffle(nums)
    return quickselect(0, n - 1, n - k)

print("\n=== Kth Largest Element ===")
print(findKthLargest([3,2,1,5,6,4], 2))      # 5
print(findKthLargest([3,2,3,1,2,4,5,5,6], 4)) # 4
# Time: O(n) average, O(n²) worst | Space: O(log n) stack

# ══════════════════════════════════════════════════════════════════
# Problem 3: Merge Intervals (LC 56)
# ══════════════════════════════════════════════════════════════════
def merge(intervals: List[List[int]]) -> List[List[int]]:
    """
    Merge all overlapping intervals.

    Approach: Sort by start. Greedily merge: if current interval's start
    <= last merged interval's end, merge (update end to max).

    Example:
      [[1,3],[2,6],[8,10],[15,18]] → [[1,6],[8,10],[15,18]]
      [[1,4],[4,5]] → [[1,5]]
    """
    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:   # overlapping
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged

print("\n=== Merge Intervals ===")
print(merge([[1,3],[2,6],[8,10],[15,18]]))  # [[1,6],[8,10],[15,18]]
print(merge([[1,4],[4,5]]))                 # [[1,5]]
# Time: O(n log n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 4: Insert Interval (LC 57)
# ══════════════════════════════════════════════════════════════════
def insert(intervals: List[List[int]], newInterval: List[int]) -> List[List[int]]:
    """
    Insert a new interval into a sorted non-overlapping list of intervals.
    Merge if necessary.

    Approach: Three phases:
    1. Add all intervals ending before newInterval starts.
    2. Merge all overlapping intervals with newInterval.
    3. Add remaining intervals.

    Example:
      [[1,3],[6,9]], newInterval=[2,5] → [[1,5],[6,9]]
      [[1,2],[3,5],[6,7],[8,10],[12,16]], newInterval=[4,8] → [[1,2],[3,10],[12,16]]
    """
    result = []
    i = 0
    n = len(intervals)

    # Phase 1: intervals completely before newInterval
    while i < n and intervals[i][1] < newInterval[0]:
        result.append(intervals[i])
        i += 1

    # Phase 2: overlapping intervals — merge
    while i < n and intervals[i][0] <= newInterval[1]:
        newInterval[0] = min(newInterval[0], intervals[i][0])
        newInterval[1] = max(newInterval[1], intervals[i][1])
        i += 1
    result.append(newInterval)

    # Phase 3: intervals completely after newInterval
    while i < n:
        result.append(intervals[i])
        i += 1

    return result

print("\n=== Insert Interval ===")
print(insert([[1,3],[6,9]], [2,5]))                          # [[1,5],[6,9]]
print(insert([[1,2],[3,5],[6,7],[8,10],[12,16]], [4,8]))     # [[1,2],[3,10],[12,16]]
# Time: O(n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 5: Non-overlapping Intervals (LC 435)
# ══════════════════════════════════════════════════════════════════
def eraseOverlapIntervals(intervals: List[List[int]]) -> int:
    """
    Find the minimum number of intervals to remove so the rest don't overlap.

    Approach: Greedy. Sort by end time. Keep interval with earliest end.
    If next interval overlaps (start < prev_end), remove it (count++).

    Example:
      [[1,2],[2,3],[3,4],[1,3]] → 1 (remove [1,3])
      [[1,2],[1,2],[1,2]] → 2
      [[1,2],[2,3]] → 0
    """
    intervals.sort(key=lambda x: x[1])  # sort by end
    removals = 0
    prev_end = float('-inf')
    for start, end in intervals:
        if start >= prev_end:
            prev_end = end   # keep this interval
        else:
            removals += 1    # remove current (it overlaps and ends later)
    return removals

print("\n=== Non-overlapping Intervals ===")
print(eraseOverlapIntervals([[1,2],[2,3],[3,4],[1,3]]))  # 1
print(eraseOverlapIntervals([[1,2],[1,2],[1,2]]))         # 2
print(eraseOverlapIntervals([[1,2],[2,3]]))               # 0
# Time: O(n log n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 6: Meeting Rooms (LC 252)
# ══════════════════════════════════════════════════════════════════
def canAttendMeetings(intervals: List[List[int]]) -> bool:
    """
    Can a person attend all meetings? Return False if any two overlap.

    Approach: Sort by start. Check if any adjacent pair overlaps.

    Example:
      [[0,30],[5,10],[15,20]] → False (overlap at 0-30 and 5-10)
      [[7,10],[2,4]] → True
    """
    intervals.sort()
    for i in range(1, len(intervals)):
        if intervals[i][0] < intervals[i-1][1]:
            return False
    return True

print("\n=== Meeting Rooms ===")
print(canAttendMeetings([[0,30],[5,10],[15,20]]))  # False
print(canAttendMeetings([[7,10],[2,4]]))            # True
# Time: O(n log n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 7: Meeting Rooms II (LC 253)
# ══════════════════════════════════════════════════════════════════
def minMeetingRooms(intervals: List[List[int]]) -> int:
    """
    Find the minimum number of conference rooms required.

    Approach: Min-heap stores end times of active meetings.
    Sort by start. For each meeting, if earliest-ending room is free
    (end <= current start), reuse it; otherwise open new room.

    Example:
      [[0,30],[5,10],[15,20]] → 2
      [[2,7]] → 1
    """
    if not intervals:
        return 0
    intervals.sort(key=lambda x: x[0])
    heap = []  # min-heap of end times

    for start, end in intervals:
        if heap and heap[0] <= start:
            heapq.heapreplace(heap, end)  # reuse freed room
        else:
            heapq.heappush(heap, end)     # open new room

    return len(heap)

print("\n=== Meeting Rooms II ===")
print(minMeetingRooms([[0,30],[5,10],[15,20]]))  # 2
print(minMeetingRooms([[2,7]]))                   # 1
print(minMeetingRooms([[1,5],[2,3],[3,7]]))       # 2
# Time: O(n log n) | Space: O(n)

# ══════════════════════════════════════════════════════════════════
# Problem 8: Sort List (LC 148) — Merge Sort on Linked List
# ══════════════════════════════════════════════════════════════════
class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

def sortList(head: Optional[ListNode]) -> Optional[ListNode]:
    """
    Sort a linked list in O(n log n) time using O(1) extra space.

    Approach: Bottom-up Merge Sort on linked list.
    Split list using slow/fast pointers, merge sorted halves.

    Example:
      4→2→1→3 → 1→2→3→4
      -1→5→3→4→0 → -1→0→3→4→5
    """
    if not head or not head.next:
        return head

    # Find midpoint using slow/fast pointers
    slow, fast = head, head.next
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next

    mid = slow.next
    slow.next = None  # split the list

    left = sortList(head)
    right = sortList(mid)
    return mergeLists(left, right)

def mergeLists(l1: Optional[ListNode], l2: Optional[ListNode]) -> Optional[ListNode]:
    dummy = ListNode(0)
    curr = dummy
    while l1 and l2:
        if l1.val <= l2.val:
            curr.next = l1; l1 = l1.next
        else:
            curr.next = l2; l2 = l2.next
        curr = curr.next
    curr.next = l1 if l1 else l2
    return dummy.next

def list_to_arr(head):
    result = []
    while head:
        result.append(head.val)
        head = head.next
    return result

def arr_to_list(arr):
    dummy = ListNode(0)
    curr = dummy
    for x in arr:
        curr.next = ListNode(x)
        curr = curr.next
    return dummy.next

print("\n=== Sort List (Merge Sort on Linked List) ===")
head = arr_to_list([4,2,1,3])
print(list_to_arr(sortList(head)))  # [1,2,3,4]
head = arr_to_list([-1,5,3,4,0])
print(list_to_arr(sortList(head)))  # [-1,0,3,4,5]
# Time: O(n log n) | Space: O(log n) stack

# ══════════════════════════════════════════════════════════════════
# Problem 9: Wiggle Sort (LC 280)
# ══════════════════════════════════════════════════════════════════
def wiggleSort(nums: List[int]) -> None:
    """
    Reorder nums in-place such that nums[0] <= nums[1] >= nums[2] <= nums[3]...

    Approach: Swap when the condition is violated.
    - If i is odd and nums[i] < nums[i-1]: swap
    - If i is even and nums[i] > nums[i-1]: swap

    Example:
      [3,5,2,1,6,4] → [3,5,1,6,2,4] (one valid answer)
    """
    for i in range(1, len(nums)):
        if (i % 2 == 1 and nums[i] < nums[i-1]) or \
           (i % 2 == 0 and nums[i] > nums[i-1]):
            nums[i], nums[i-1] = nums[i-1], nums[i]

print("\n=== Wiggle Sort ===")
nums = [3,5,2,1,6,4]
wiggleSort(nums)
print(nums)  # some valid wiggle arrangement
# Verify: check alternating pattern
valid = all(
    (nums[i] <= nums[i+1] if i % 2 == 0 else nums[i] >= nums[i+1])
    for i in range(len(nums)-1)
)
print(f"Valid wiggle: {valid}")
# Time: O(n) | Space: O(1)

# ══════════════════════════════════════════════════════════════════
# Problem 10: Largest Number (LC 179)
# ══════════════════════════════════════════════════════════════════
def largestNumber(nums: List[int]) -> str:
    """
    Arrange numbers to form the largest number.

    Approach: Custom comparator. For two numbers a and b,
    compare str(a)+str(b) vs str(b)+str(a).
    Sort descending by this comparison.

    Example:
      [10,2] → "210"
      [3,30,34,5,9] → "9534330"
    """
    strs = [str(x) for x in nums]

    def compare(a, b):
        if a + b > b + a: return -1  # a should come first
        elif a + b < b + a: return 1
        return 0

    strs.sort(key=cmp_to_key(compare))

    result = ''.join(strs)
    return '0' if result[0] == '0' else result  # handle [0,0]

print("\n=== Largest Number ===")
print(largestNumber([10,2]))          # "210"
print(largestNumber([3,30,34,5,9]))   # "9534330"
print(largestNumber([0,0]))           # "0"
# Time: O(n log n * k) where k = avg digit length | Space: O(n)

print("\n✓ All 10 Sorting Algorithm problems solved!")
