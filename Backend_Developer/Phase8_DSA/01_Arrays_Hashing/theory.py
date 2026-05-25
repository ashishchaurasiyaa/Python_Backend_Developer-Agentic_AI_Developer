"""
01 — Arrays & Hashing — Theory
================================
Level  : Basic → Intermediate
Pattern: WHAT → WHY → HOW → Complexity → Python Tips → Q&A
"""

# ════════════════════════════════════════════════════════════
# WHAT
# ════════════════════════════════════════════════════════════
"""
ARRAY  — Contiguous block of memory, same-type elements, O(1) random access.
         Python equivalent: list  (dynamic array, auto-resizes)

HASHING — Converts a key into an index using a hash function.
          Python equivalent: dict / set  (hash table under the hood)

WHY HASHING?
  Without hash: finding element in list = O(n) scan
  With hash:    finding element in dict = O(1) average
"""

# ════════════════════════════════════════════════════════════
# COMPLEXITY TABLE
# ════════════════════════════════════════════════════════════
"""
Operation        List (Array)    Dict/Set (Hash)
─────────────────────────────────────────────────
Access by index  O(1)            —
Search           O(n)            O(1) avg
Insert at end    O(1) amortized  O(1) avg
Insert at start  O(n)            O(1) avg
Delete           O(n)            O(1) avg
Space            O(n)            O(n)
"""

# ════════════════════════════════════════════════════════════
# PYTHON ARRAY OPERATIONS
# ════════════════════════════════════════════════════════════

arr = [3, 1, 4, 1, 5, 9, 2, 6]

# Basic operations
print(arr[0])           # O(1) — index access
print(arr[-1])          # O(1) — last element
print(arr[1:4])         # O(k) — slicing
arr.append(7)           # O(1) amortized
arr.insert(0, 0)        # O(n) — shifts elements
arr.pop()               # O(1) — remove last
arr.pop(0)              # O(n) — remove first
arr.remove(1)           # O(n) — remove first occurrence of value
print(len(arr))         # O(1)
print(arr.index(5))     # O(n) — find index of value
print(5 in arr)         # O(n) — membership test (use set for O(1))

# Sorting
arr.sort()              # O(n log n) — in-place
sorted_arr = sorted(arr, reverse=True)  # O(n log n) — new list
arr.sort(key=lambda x: -x)             # sort by custom key

# ════════════════════════════════════════════════════════════
# HASHING — dict and set
# ════════════════════════════════════════════════════════════

# Dict — key: value pairs
freq = {}
for num in [1, 2, 2, 3, 3, 3]:
    freq[num] = freq.get(num, 0) + 1
print(freq)   # {1:1, 2:2, 3:3}

# Cleaner with defaultdict
from collections import defaultdict, Counter

freq2 = defaultdict(int)
for num in [1, 2, 2, 3, 3, 3]:
    freq2[num] += 1

# Cleanest with Counter
freq3 = Counter([1, 2, 2, 3, 3, 3])
print(freq3.most_common(2))   # [(3, 3), (2, 2)]

# Set — unique elements, O(1) lookup
seen  = set()
nums  = [1, 2, 2, 3, 4, 4]
dupes = [x for x in nums if x in seen or seen.add(x)]  # track duplicates

# Set operations
a = {1, 2, 3, 4}
b = {3, 4, 5, 6}
print(a & b)    # intersection: {3, 4}
print(a | b)    # union: {1,2,3,4,5,6}
print(a - b)    # difference: {1, 2}
print(a ^ b)    # symmetric diff: {1, 2, 5, 6}

# ════════════════════════════════════════════════════════════
# KEY PATTERNS (interview patterns)
# ════════════════════════════════════════════════════════════

# PATTERN 1: Frequency Map
def pattern_frequency(arr):
    """Count occurrences of each element."""
    return Counter(arr)

# PATTERN 2: Two-Pass (first pass build map, second pass use it)
def two_pass_example(nums):
    seen = set(nums)          # pass 1: build set
    result = []
    for n in nums:            # pass 2: use set for O(1) lookup
        if (n - 1) not in seen:
            result.append(n)
    return result

# PATTERN 3: Complement / Pair lookup
def find_pair(nums, target):
    """Find two numbers that sum to target — O(n)."""
    seen = {}
    for i, n in enumerate(nums):
        complement = target - n
        if complement in seen:
            return [seen[complement], i]
        seen[n] = i
    return []

# PATTERN 4: Prefix Sum
def prefix_sum(nums):
    """Build prefix sum array for range-sum queries in O(1)."""
    prefix = [0] * (len(nums) + 1)
    for i, n in enumerate(nums):
        prefix[i + 1] = prefix[i] + n
    return prefix

def range_sum(prefix, left, right) -> int:
    """Sum of nums[left..right] in O(1) after O(n) preprocessing."""
    return prefix[right + 1] - prefix[left]

# PATTERN 5: Bucket / Pigeonhole
def bucket_pattern(nums):
    """Use array index as bucket for O(n) grouping."""
    buckets = defaultdict(list)
    for n in nums:
        buckets[len(str(n))].append(n)   # group by digit count
    return buckets

# ════════════════════════════════════════════════════════════
# COMMON MISTAKES
# ════════════════════════════════════════════════════════════
"""
❌ Using list for membership test inside loop → O(n²)
   for x in data:
       if x in my_list:   ← O(n) per check!

✅ Convert to set first → O(n) total
   my_set = set(my_list)
   for x in data:
       if x in my_set:   ← O(1) per check

❌ Modifying list while iterating
   for i, x in enumerate(arr):
       if x < 0: arr.remove(x)   ← skips elements!

✅ Iterate over copy or use list comprehension
   arr = [x for x in arr if x >= 0]
"""

# ════════════════════════════════════════════════════════════
# INTERVIEW Q&A
# ════════════════════════════════════════════════════════════
"""
Q: What is the time complexity of dict.get()?
A: O(1) average, O(n) worst case (hash collision). In practice always O(1).

Q: Why does list.insert(0, x) take O(n)?
A: Python list is a dynamic array. Inserting at start shifts ALL elements right by 1.
   Use collections.deque for O(1) insert at both ends.

Q: How does Python handle hash collisions?
A: Open addressing (probing). Python dict resizes when 2/3 full to maintain performance.

Q: When to use list vs set?
A: List: need order, allow duplicates, need index access.
   Set: need O(1) lookup, unique elements only, no order needed.

Q: What is the difference between is and ==?
A: == checks value equality. is checks identity (same object in memory).
   Small ints (-5 to 256) are interned: (256 is 256) → True.
   Large ints: (257 is 257) may be False.
"""
