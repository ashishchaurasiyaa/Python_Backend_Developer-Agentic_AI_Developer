"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAMBDA, MAP, FILTER, ZIP, SORTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ARCHITECTURE UNDERSTANDING:
  Lambda = anonymous function — one expression only
  Map    = apply function to every element → lazy iterator
  Filter = keep elements where function returns True → lazy iterator
  Zip    = combine multiple iterables element by element
  Sorted = return sorted list (uses key function)

  WHY FUNCTIONAL STYLE?
  → Composable — chain transformations
  → No side effects — predictable
  → Modern Python: comprehensions often preferred over map/filter
    but lambda + sorted + key= is used everywhere

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from functools import reduce

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. LAMBDA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: Lambda vs def?
A: Lambda = anonymous, single expression, no statements, no docstring
   def    = named, multiple lines, can have anything
   Use lambda only when: key= argument, small throwaway function
"""

# Syntax: lambda args: expression
square = lambda x: x ** 2
add    = lambda x, y: x + y
greet  = lambda name: f"Hello, {name}!"

print(square(5))        # 25
print(add(3, 4))        # 7
print(greet("Ashish"))  # Hello, Ashish!

# Default argument in lambda
power = lambda x, n=2: x ** n
print(power(3))         # 9
print(power(3, 3))      # 27

# Lambda in sorted (MOST COMMON USE CASE)
employees = [
    {"name": "Ashish", "salary": 80000, "age": 28},
    {"name": "Priya",  "salary": 90000, "age": 25},
    {"name": "Rahul",  "salary": 75000, "age": 30},
]

# Sort by salary
by_salary = sorted(employees, key=lambda e: e["salary"])
print([e["name"] for e in by_salary])   # ['Rahul', 'Ashish', 'Priya']

# Sort by multiple fields (name then age)
by_name_age = sorted(employees, key=lambda e: (e["name"], e["age"]))

# Sort descending
by_salary_desc = sorted(employees, key=lambda e: e["salary"], reverse=True)

# Sort strings case-insensitive
words = ["Banana", "apple", "Cherry"]
sorted_words = sorted(words, key=lambda w: w.lower())
print(sorted_words)     # ['apple', 'Banana', 'Cherry']

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. MAP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: map() vs list comprehension?
A: map() is lazy (iterator), slightly faster for built-in functions
   list comprehension is more Pythonic and readable for custom logic
   map(str, numbers) is cleaner than [str(x) for x in numbers]
"""

numbers = [1, 2, 3, 4, 5]

# Basic map
squares = list(map(lambda x: x ** 2, numbers))
print(squares)          # [1, 4, 9, 16, 25]

# map with built-in function (most common real use)
str_numbers = list(map(str, numbers))   # [str(1), str(2), ...]
print(str_numbers)      # ['1', '2', '3', '4', '5']

int_strings = list(map(int, ["1", "2", "3"]))   # string → int
print(int_strings)      # [1, 2, 3]

# map with multiple iterables
a = [1, 2, 3]
b = [10, 20, 30]
sums = list(map(lambda x, y: x + y, a, b))
print(sums)             # [11, 22, 33]

# Real use: parse CSV row
row = "Ashish,28,80000"
fields = list(map(str.strip, row.split(",")))   # clean whitespace
print(fields)           # ['Ashish', '28', '80000']

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. FILTER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: filter() vs comprehension with if?
A: filter() is lazy iterator, slightly cleaner for simple boolean functions
   [x for x in data if func(x)]  ← more readable for most cases
   filter(None, data) ← special: removes all falsy values (0, '', None, [])
"""

numbers = [1, -2, 3, -4, 5, -6, 0]

# Filter positive numbers
positives = list(filter(lambda x: x > 0, numbers))
print(positives)        # [1, 3, 5]

# filter(None, ...) — removes falsy values (very common pattern)
mixed = [1, 0, "hello", "", None, [], [1, 2], False, True]
truthy = list(filter(None, mixed))
print(truthy)           # [1, 'hello', [1, 2], True]

# Combining map + filter
even_squares = list(map(lambda x: x**2, filter(lambda x: x%2==0, range(10))))
print(even_squares)     # [0, 4, 16, 36, 64]
# Same as: [x**2 for x in range(10) if x%2==0]   ← this is cleaner

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. ZIP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: zip() real use?
A: Parallel iteration, create dicts from two lists, matrix transpose
"""

names  = ["Alice", "Bob", "Charlie"]
scores = [85, 92, 78]
grades = ["B", "A", "C"]

# Basic zip — pair up elements
for name, score in zip(names, scores):
    print(f"{name}: {score}")

# Create dict from two lists (very common)
score_dict = dict(zip(names, scores))
print(score_dict)       # {'Alice': 85, 'Bob': 92, 'Charlie': 78}

# Zip multiple iterables
for name, score, grade in zip(names, scores, grades):
    print(f"{name}: {score} ({grade})")

# zip stops at shortest — use zip_longest for unequal lengths
from itertools import zip_longest
a = [1, 2, 3]
b = [10, 20]
pairs = list(zip_longest(a, b, fillvalue=0))
print(pairs)            # [(1, 10), (2, 20), (3, 0)]

# Unzip — * operator trick
pairs = [(1, "a"), (2, "b"), (3, "c")]
nums, letters = zip(*pairs)    # unpack and transpose
print(nums)             # (1, 2, 3)
print(letters)          # ('a', 'b', 'c')

# Matrix transpose using zip
matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
transposed = list(map(list, zip(*matrix)))
print(transposed)       # [[1, 4, 7], [2, 5, 8], [3, 6, 9]]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. ENUMERATE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

fruits = ["apple", "banana", "cherry"]

# Bad: using range(len(...))
for i in range(len(fruits)):            # don't do this
    print(i, fruits[i])

# Good: enumerate
for i, fruit in enumerate(fruits):      # Pythonic
    print(i, fruit)

# With custom start
for i, fruit in enumerate(fruits, start=1):
    print(f"{i}. {fruit}")              # 1. apple, 2. banana...

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. REDUCE (functools)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: When to use reduce?
A: When you need to accumulate a collection into a single value.
   sum(), max(), min() are built-in reduces for common cases.
   reduce() for custom accumulation logic.
"""

from functools import reduce

numbers = [1, 2, 3, 4, 5]

total   = reduce(lambda acc, x: acc + x, numbers)        # 15 (same as sum())
product = reduce(lambda acc, x: acc * x, numbers)        # 120
maximum = reduce(lambda a, b: a if a > b else b, numbers)# 5 (same as max())

# Practical: flatten list of lists
nested = [[1, 2], [3, 4], [5, 6]]
flat = reduce(lambda acc, x: acc + x, nested)
print(flat)             # [1, 2, 3, 4, 5, 6]

# Build dict from list of tuples
pairs = [("a", 1), ("b", 2), ("c", 3)]
d = reduce(lambda acc, pair: {**acc, pair[0]: pair[1]}, pairs, {})
print(d)                # {'a': 1, 'b': 2, 'c': 3}

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW Q&A:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: Lambda limitations?
A: - Single expression only (no if/else blocks, no loops)
   - No docstring → debugging harder
   - Can't have type annotations
   - Prefer named function for complex logic

Q: map() vs list comprehension — which is faster?
A: map(built_in, list) is marginally faster (no Python function call overhead)
   map(lambda, list) ≈ same as list comprehension
   In practice: use list comprehension for readability

Q: When does zip() stop?
A: At the SHORTEST iterable. Use itertools.zip_longest() if you
   want to process all elements (fills missing with fillvalue).

Q: What does sorted() return?
A: Always a NEW list. It never modifies the original.
   list.sort() → modifies in place, returns None.
   Use sorted() for immutable data / tuples / generators.
"""
