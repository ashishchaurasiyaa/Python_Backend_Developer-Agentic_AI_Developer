"""
╔══════════════════════════════════════════════════════════════════╗
║            SORTING ALGORITHMS — Complete Theory Guide            ║
╚══════════════════════════════════════════════════════════════════╝

COMPLEXITY TABLE
─────────────────────────────────────────────────────────────────
Algorithm      Best        Average     Worst       Space    Stable?
─────────────────────────────────────────────────────────────────
Bubble         O(n)        O(n²)       O(n²)       O(1)     Yes
Selection      O(n²)       O(n²)       O(n²)       O(1)     No
Insertion      O(n)        O(n²)       O(n²)       O(1)     Yes
Merge          O(n log n)  O(n log n)  O(n log n)  O(n)     Yes
Quick          O(n log n)  O(n log n)  O(n²)       O(log n) No
Heap           O(n log n)  O(n log n)  O(n log n)  O(1)     No
Counting       O(n+k)      O(n+k)      O(n+k)      O(k)     Yes
Radix          O(nk)       O(nk)       O(nk)       O(n+k)   Yes
Tim (Python)   O(n)        O(n log n)  O(n log n)  O(n)     Yes
─────────────────────────────────────────────────────────────────
k = range of input values
"""

from typing import List
import heapq

# ─────────────────────────────────────────────
# 1. BUBBLE SORT
# ─────────────────────────────────────────────
print("=" * 60)
print("1. BUBBLE SORT")
print("=" * 60)

"""
HOW: Compare adjacent elements, swap if out of order. Repeat n times.
The largest element "bubbles up" to the correct position each pass.
WHEN TO USE: Never in practice. Useful for teaching only.
STABLE: Yes (only swaps when strictly less, so equals stay in order)
"""

def bubble_sort(arr: List[int]) -> List[int]:
    arr = arr[:]
    n = len(arr)
    for i in range(n):
        swapped = False
        for j in range(n - i - 1):  # last i elements already sorted
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
                swapped = True
        if not swapped:
            break  # optimization: already sorted
    return arr

arr = [64, 34, 25, 12, 22, 11, 90]
print(f"Input:  {arr}")
print(f"Sorted: {bubble_sort(arr)}")
# Time: O(n²) | Space: O(1)

# ─────────────────────────────────────────────
# 2. SELECTION SORT
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("2. SELECTION SORT")
print("=" * 60)

"""
HOW: Find the minimum of the unsorted portion, swap it to the front.
WHEN TO USE: When memory writes are expensive (minimizes swaps to O(n)).
STABLE: No (can skip over equal elements when swapping)
"""

def selection_sort(arr: List[int]) -> List[int]:
    arr = arr[:]
    n = len(arr)
    for i in range(n):
        min_idx = i
        for j in range(i+1, n):
            if arr[j] < arr[min_idx]:
                min_idx = j
        arr[i], arr[min_idx] = arr[min_idx], arr[i]
    return arr

arr = [64, 25, 12, 22, 11]
print(f"Input:  {arr}")
print(f"Sorted: {selection_sort(arr)}")
# Time: O(n²) | Space: O(1)

# ─────────────────────────────────────────────
# 3. INSERTION SORT
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("3. INSERTION SORT")
print("=" * 60)

"""
HOW: Build sorted array one element at a time. Insert each element
into its correct position in the sorted portion.
WHEN TO USE: Small arrays (n < 20), nearly sorted data, online sorting.
Python's Timsort uses insertion sort for small subarrays.
STABLE: Yes
"""

def insertion_sort(arr: List[int]) -> List[int]:
    arr = arr[:]
    for i in range(1, len(arr)):
        key = arr[i]
        j = i - 1
        while j >= 0 and arr[j] > key:
            arr[j+1] = arr[j]  # shift right
            j -= 1
        arr[j+1] = key         # insert key
    return arr

arr = [12, 11, 13, 5, 6]
print(f"Input:  {arr}")
print(f"Sorted: {insertion_sort(arr)}")
# Time: O(n²) avg, O(n) nearly sorted | Space: O(1)

# ─────────────────────────────────────────────
# 4. MERGE SORT
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("4. MERGE SORT — Divide and Conquer")
print("=" * 60)

"""
HOW: Divide array in half, recursively sort each half, merge sorted halves.
WHEN TO USE: When stable sort needed, external sorting (data doesn't fit in RAM),
linked lists (no random access), guaranteed O(n log n).
STABLE: Yes
KEY: The merge step is O(n). With log n levels → O(n log n) total.
"""

def merge_sort(arr: List[int]) -> List[int]:
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])
    return merge(left, right)

def merge(left: List[int], right: List[int]) -> List[int]:
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i]); i += 1
        else:
            result.append(right[j]); j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result

arr = [38, 27, 43, 3, 9, 82, 10]
print(f"Input:  {arr}")
print(f"Sorted: {merge_sort(arr)}")
# Time: O(n log n) all cases | Space: O(n)

# ─────────────────────────────────────────────
# 5. QUICK SORT
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("5. QUICK SORT — Divide and Conquer (In-Place)")
print("=" * 60)

"""
HOW: Choose a pivot. Partition: put smaller elements left, larger right.
Recursively sort both partitions.
WHEN TO USE: In-place sorting, average-case fastest in practice.
AVOID: When worst-case O(n²) is unacceptable (nearly sorted arrays with bad pivot).
STABLE: No
PIVOT STRATEGIES: Last element, first element, random, median-of-three.
"""

def quick_sort(arr: List[int], lo: int = 0, hi: int = -1) -> None:
    if hi == -1:
        hi = len(arr) - 1
    if lo < hi:
        pivot_idx = partition(arr, lo, hi)
        quick_sort(arr, lo, pivot_idx - 1)
        quick_sort(arr, pivot_idx + 1, hi)

def partition(arr: List[int], lo: int, hi: int) -> int:
    """Lomuto partition scheme: pivot = arr[hi]."""
    pivot = arr[hi]
    i = lo - 1  # boundary of smaller elements
    for j in range(lo, hi):
        if arr[j] <= pivot:
            i += 1
            arr[i], arr[j] = arr[j], arr[i]
    arr[i+1], arr[hi] = arr[hi], arr[i+1]
    return i + 1

arr = [10, 7, 8, 9, 1, 5]
print(f"Input:  {arr}")
quick_sort(arr)
print(f"Sorted: {arr}")
# Time: O(n log n) avg, O(n²) worst | Space: O(log n) stack

# ─────────────────────────────────────────────
# 6. HEAP SORT
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("6. HEAP SORT")
print("=" * 60)

"""
HOW: Build a max-heap. Repeatedly extract max (swap root with last,
heapify root). Result is sorted ascending.
WHEN TO USE: Guaranteed O(n log n) with O(1) space. Not stable.
Used in: selection algorithms (kth largest), priority queues.
STABLE: No
"""

def heap_sort(arr: List[int]) -> List[int]:
    arr = arr[:]
    n = len(arr)

    def heapify(arr, n, i):
        largest = i
        left = 2 * i + 1
        right = 2 * i + 2
        if left < n and arr[left] > arr[largest]:
            largest = left
        if right < n and arr[right] > arr[largest]:
            largest = right
        if largest != i:
            arr[i], arr[largest] = arr[largest], arr[i]
            heapify(arr, n, largest)

    # Build max-heap
    for i in range(n // 2 - 1, -1, -1):
        heapify(arr, n, i)

    # Extract elements one by one
    for i in range(n - 1, 0, -1):
        arr[0], arr[i] = arr[i], arr[0]  # move max to end
        heapify(arr, i, 0)

    return arr

arr = [12, 11, 13, 5, 6, 7]
print(f"Input:  {arr}")
print(f"Sorted: {heap_sort(arr)}")
# Time: O(n log n) all cases | Space: O(1)

# ─────────────────────────────────────────────
# 7. COUNTING SORT
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("7. COUNTING SORT — Linear Time (Non-Comparison)")
print("=" * 60)

"""
HOW: Count frequency of each value. Compute prefix sums for positions.
Place each element at its correct position.
WHEN TO USE: Integer keys in a small range (k << n).
AVOID: Large range or non-integer keys.
STABLE: Yes
TIME: O(n + k) where k = range of values.
"""

def counting_sort(arr: List[int]) -> List[int]:
    if not arr:
        return arr
    min_val, max_val = min(arr), max(arr)
    k = max_val - min_val + 1
    count = [0] * k
    for x in arr:
        count[x - min_val] += 1
    result = []
    for i, c in enumerate(count):
        result.extend([i + min_val] * c)
    return result

arr = [4, 2, 2, 8, 3, 3, 1]
print(f"Input:  {arr}")
print(f"Sorted: {counting_sort(arr)}")
# Time: O(n + k) | Space: O(k)

# ─────────────────────────────────────────────
# 8. RADIX SORT
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("8. RADIX SORT — Digit by Digit")
print("=" * 60)

"""
HOW: Sort by each digit, from least significant to most significant.
Use a stable sort (counting sort) at each digit level.
WHEN TO USE: Large integers or fixed-length strings with small alphabet.
STABLE: Yes
TIME: O(nk) where k = number of digits.
"""

def radix_sort(arr: List[int]) -> List[int]:
    if not arr:
        return arr
    max_val = max(arr)
    exp = 1
    while max_val // exp > 0:
        arr = counting_sort_by_digit(arr, exp)
        exp *= 10
    return arr

def counting_sort_by_digit(arr: List[int], exp: int) -> List[int]:
    n = len(arr)
    output = [0] * n
    count = [0] * 10
    for x in arr:
        digit = (x // exp) % 10
        count[digit] += 1
    for i in range(1, 10):
        count[i] += count[i-1]
    for i in range(n-1, -1, -1):  # traverse right to left for stability
        digit = (arr[i] // exp) % 10
        output[count[digit] - 1] = arr[i]
        count[digit] -= 1
    return output

arr = [170, 45, 75, 90, 802, 24, 2, 66]
print(f"Input:  {arr}")
print(f"Sorted: {radix_sort(arr)}")
# Time: O(nk) | Space: O(n + k)

# ─────────────────────────────────────────────
# 9. PYTHON'S BUILT-IN SORT (TIMSORT)
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("9. PYTHON'S BUILT-IN SORT — Timsort")
print("=" * 60)

"""
Python uses Timsort — a hybrid of merge sort and insertion sort.
  - O(n log n) worst case, O(n) best case (already sorted)
  - Stable, in-place for list.sort(), creates new list for sorted()

ALWAYS prefer Python's built-in sort in interviews unless the problem
specifically asks you to implement a sorting algorithm.

Key usage:
  arr.sort()                     # in-place, returns None
  sorted(arr)                    # creates new list
  arr.sort(key=lambda x: x[1])  # sort by second element
  arr.sort(reverse=True)        # descending
  arr.sort(key=abs)             # sort by absolute value
"""

data = [(1, 'b'), (3, 'a'), (2, 'c')]
print(sorted(data, key=lambda x: x[1]))  # sort by letter
print(sorted([3,-1,2,-4], key=abs))      # [−1,2,3,−4]

# ─────────────────────────────────────────────
# 10. INTERVIEW Q&A
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("INTERVIEW Q&A")
print("=" * 60)

qa = """
Q1: Why is Merge Sort preferred for linked lists over Quick Sort?
A1: Linked lists lack random access, so finding the pivot in Quick Sort
    takes O(n). Merge Sort only needs sequential access, making it O(n log n).
    Also, Merge Sort's merge step works naturally with linked list pointers.

Q2: When does Quick Sort degrade to O(n²)?
A2: When the pivot is always the smallest or largest element (sorted input).
    Fix: use random pivot or median-of-three pivot selection.

Q3: What does "stable" sorting mean?
A3: Elements with equal keys maintain their original relative order.
    Important when: sorting by one key then another (multi-key sort),
    or when the data has associated metadata.

Q4: Why can Counting/Radix Sort beat the O(n log n) lower bound?
A4: The O(n log n) lower bound applies only to COMPARISON-based sorts.
    Counting and Radix sort exploit the structure of integer keys (not comparisons).

Q5: Which sorting algorithm does Python use and why?
A5: Timsort. It's O(n) on nearly-sorted data (very common in practice),
    O(n log n) worst case, stable, and efficient for real-world data.

Q6: When would you use Heap Sort over Merge Sort?
A6: When you need O(1) extra space AND don't need stability.
    Merge Sort needs O(n) extra space. Heap Sort is in-place.

Q7: What is the space complexity of recursive Quick Sort?
A7: O(log n) average for the call stack. O(n) worst case (unbalanced).
    With tail recursion optimization, can achieve O(log n) always.

Q8: What is the Dutch National Flag problem?
A8: Partition an array into three groups (e.g., 0s, 1s, 2s) in O(n) time.
    Uses a 3-way partitioning variant of Quick Sort (Dijkstra's algorithm).
"""
print(qa)
