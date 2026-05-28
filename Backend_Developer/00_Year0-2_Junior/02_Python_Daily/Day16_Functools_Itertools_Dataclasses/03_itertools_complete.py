"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ITERTOOLS MODULE — Complete Guide
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ARCHITECTURE UNDERSTANDING:
  itertools = standard library tools for iterator algebra
  ALL itertools functions return LAZY iterators (memory efficient)
  They work on ANY iterable (list, generator, file, etc.)

  THREE CATEGORIES:
  1. Infinite iterators     → count, cycle, repeat
  2. Finite iterators       → chain, islice, takewhile, groupby, etc.
  3. Combinatoric iterators → product, permutations, combinations

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import itertools

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. INFINITE ITERATORS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

# count(start, step) — infinite counter
counter = itertools.count(start=1, step=2)
first_five_odd = list(itertools.islice(counter, 5))
print(first_five_odd)       # [1, 3, 5, 7, 9]

# cycle(iterable) — infinite repetition
status_cycle = itertools.cycle(["pending", "processing", "done"])
statuses = [next(status_cycle) for _ in range(7)]
print(statuses)             # ['pending', 'processing', 'done', 'pending', 'processing', 'done', 'pending']

# repeat(object, times=None) — repeat N times or forever
three_zeros = list(itertools.repeat(0, 3))
print(three_zeros)          # [0, 0, 0]

# Practical: enumerate with custom counter
ids = itertools.count(1000)
users = ["Alice", "Bob", "Charlie"]
for user_id, name in zip(ids, users):
    print(f"ID {user_id}: {name}")     # ID 1000: Alice, ID 1001: Bob...

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. CHAIN — FLATTEN / MERGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: chain vs chain.from_iterable?
A: chain(*iterables) → when you have separate iterables
   chain.from_iterable(iterable_of_iterables) → when you have one iterable
   containing others (avoids unpacking with *)
"""

# Merge multiple iterables
a, b, c = [1, 2], [3, 4], [5, 6]
merged = list(itertools.chain(a, b, c))
print(merged)               # [1, 2, 3, 4, 5, 6]

# chain.from_iterable — flatten one level
nested = [[1, 2], [3, 4], [5, 6]]
flat = list(itertools.chain.from_iterable(nested))
print(flat)                 # [1, 2, 3, 4, 5, 6]

# Real use: merge multiple DB results
page1 = [{"id": 1}, {"id": 2}]
page2 = [{"id": 3}, {"id": 4}]
page3 = [{"id": 5}]
all_results = list(itertools.chain(page1, page2, page3))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. ISLICE — SLICE A GENERATOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

def infinite_sequence():
    n = 0
    while True:
        yield n
        n += 1

# Take first 10 from infinite generator
first_10 = list(itertools.islice(infinite_sequence(), 10))
print(first_10)             # [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

# islice(iterable, start, stop, step)
every_other = list(itertools.islice(range(20), 0, 20, 2))
print(every_other)          # [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. TAKEWHILE / DROPWHILE — CONDITIONAL SLICE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

numbers = [2, 4, 6, 7, 8, 10, 3, 1]

# takewhile: take elements WHILE condition is True, STOP at first False
evens = list(itertools.takewhile(lambda x: x % 2 == 0, numbers))
print(evens)                # [2, 4, 6]  ← stops at 7

# dropwhile: skip elements WHILE condition is True, START after first False
after_odd = list(itertools.dropwhile(lambda x: x % 2 == 0, numbers))
print(after_odd)            # [7, 8, 10, 3, 1]  ← starts from 7

# Real use: skip log file header
log_lines = ["# Header", "# Config", "# Start", "INFO: Server started", "INFO: Ready"]
actual_logs = list(itertools.dropwhile(lambda x: x.startswith("#"), log_lines))
print(actual_logs)          # ['INFO: Server started', 'INFO: Ready']

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. GROUPBY — GROUP CONSECUTIVE ELEMENTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
CRITICAL: groupby only groups CONSECUTIVE equal elements.
Input MUST be sorted by the key you're grouping on.
"""

employees = [
    {"dept": "Engineering", "name": "Alice"},
    {"dept": "Engineering", "name": "Bob"},
    {"dept": "Marketing",   "name": "Carol"},
    {"dept": "Marketing",   "name": "Dave"},
    {"dept": "Engineering", "name": "Eve"},   # ← NOT grouped with Alice/Bob!
]

# Sort first, then groupby
sorted_emps = sorted(employees, key=lambda e: e["dept"])

for dept, group in itertools.groupby(sorted_emps, key=lambda e: e["dept"]):
    names = [e["name"] for e in group]
    print(f"{dept}: {names}")
# Engineering: ['Alice', 'Bob', 'Eve']
# Marketing: ['Carol', 'Dave']

# Run-length encoding using groupby
def run_length_encode(s: str) -> list[tuple[str, int]]:
    return [(char, len(list(group))) for char, group in itertools.groupby(s)]

print(run_length_encode("AAABBBCCDDDDEE"))
# [('A', 3), ('B', 3), ('C', 2), ('D', 4), ('E', 2)]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. COMBINATORIC ITERATORS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: product vs permutations vs combinations — difference?
A: product(a, b)           → Cartesian product (with replacement)
   permutations(a, r)      → all ordered arrangements of r items
   combinations(a, r)      → all unordered selections of r items (no repeat)
   combinations_with_replacement(a, r) → unordered, repeats allowed
"""

items = ["A", "B", "C"]

# Cartesian product (nested loop replacement)
# product([1,2], [3,4]) = [(1,3),(1,4),(2,3),(2,4)]
for x, y in itertools.product([1, 2], [3, 4]):
    print(f"({x},{y})", end=" ")
print()     # (1,3) (1,4) (2,3) (2,4)

# Dice roll simulation: all combinations of two dice
dice_rolls = list(itertools.product(range(1, 7), repeat=2))
print(f"Total dice combinations: {len(dice_rolls)}")    # 36

# Permutations (order matters): ABC, ACB, BAC, BCA, CAB, CBA
perms = list(itertools.permutations(items))
print(f"Permutations of ABC: {len(perms)}")     # 6

# r-length permutations
perms_2 = list(itertools.permutations(items, 2))
print(perms_2)  # [('A','B'), ('A','C'), ('B','A'), ('B','C'), ('C','A'), ('C','B')]

# Combinations (order doesn't matter): AB, AC, BC
combos = list(itertools.combinations(items, 2))
print(combos)   # [('A', 'B'), ('A', 'C'), ('B', 'C')]

# Real use: test all parameter combinations
def test_config(batch_size, learning_rate, dropout):
    print(f"Testing: batch={batch_size}, lr={learning_rate}, drop={dropout}")

batch_sizes    = [32, 64, 128]
learning_rates = [0.001, 0.01]
dropouts       = [0.1, 0.3]

for config in itertools.product(batch_sizes, learning_rates, dropouts):
    test_config(*config)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. ZIP_LONGEST AND STARMAP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

# zip_longest: zip but pads shorter iterables
a = [1, 2, 3, 4, 5]
b = [10, 20]
padded = list(itertools.zip_longest(a, b, fillvalue=0))
print(padded)   # [(1,10), (2,20), (3,0), (4,0), (5,0)]

# starmap: like map but unpacks each element as args
pairs = [(2, 3), (4, 2), (10, 3)]
import operator
results = list(itertools.starmap(pow, pairs))
print(results)  # [8, 16, 1000]   ← pow(2,3), pow(4,2), pow(10,3)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 8. ACCUMULATE — RUNNING TOTALS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

import operator

sales = [100, 200, 150, 300, 250]

# Running sum
running_total = list(itertools.accumulate(sales))
print(running_total)    # [100, 300, 450, 750, 1000]

# Running maximum
running_max = list(itertools.accumulate(sales, func=max))
print(running_max)      # [100, 200, 200, 300, 300]

# Running product
running_product = list(itertools.accumulate([1, 2, 3, 4, 5], func=operator.mul))
print(running_product)  # [1, 2, 6, 24, 120]

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW Q&A:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: itertools kyun use karte hain?
A: All lazy iterators → O(1) memory regardless of input size.
   Highly optimized C implementation — faster than Python loops.

Q: groupby gotcha kya hai?
A: Only groups CONSECUTIVE equal elements. MUST sort first.
   If not sorted: same key will appear in multiple groups.

Q: combinations vs permutations?
A: combinations('ABC', 2) → AB, AC, BC     (order doesn't matter, 3 results)
   permutations('ABC', 2) → AB, AC, BA, BC, CA, CB (order matters, 6 results)

Q: When to use product?
A: Nested for loops ko replace karo — cleaner, works on any number of iterables.
   for a in A: for b in B: → itertools.product(A, B)
"""
