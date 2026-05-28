"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPREHENSIONS — List, Dict, Set, Generator
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ARCHITECTURE UNDERSTANDING:
  Comprehension = compact syntax for creating collections
  from existing iterables.

  Syntax:  [expression  for item in iterable  if condition]
            ┌─output─┐  ┌────iteration────┐   ┌─filter─┐

  WHY USE COMPREHENSIONS?
  → Pythonic, readable, faster than equivalent for loop
  → Avoids .append() boilerplate
  → List comp runs ~35% faster than for loop (C-level optimized)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. LIST COMPREHENSION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# Basic: transform
squares = [x ** 2 for x in numbers]
print(squares)          # [1, 4, 9, 16, 25, ...]

# With filter (if condition)
even_squares = [x ** 2 for x in numbers if x % 2 == 0]
print(even_squares)     # [4, 16, 36, 64, 100]

# Equivalent for loop (verbose):
result = []
for x in numbers:
    if x % 2 == 0:
        result.append(x ** 2)

# If-else inside comprehension (ternary)
labels = ["even" if x % 2 == 0 else "odd" for x in numbers]
print(labels)           # ['odd', 'even', 'odd', 'even', ...]

# Nested loops (flattening 2D list)
matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
flat = [num for row in matrix for num in row]
print(flat)             # [1, 2, 3, 4, 5, 6, 7, 8, 9]

# String processing
words = ["  hello  ", "  world  ", "  python  "]
cleaned = [w.strip().title() for w in words]
print(cleaned)          # ['Hello', 'World', 'Python']

# Filter None values
data = [1, None, 2, None, 3, None, 4]
clean_data = [x for x in data if x is not None]
print(clean_data)       # [1, 2, 3, 4]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. DICT COMPREHENSION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: Dict comprehension ka real use case?
A: Transform/filter dicts, invert key-value, group data
"""

# Basic: create dict from list
names = ["ashish", "priya", "rahul"]
name_lengths = {name: len(name) for name in names}
print(name_lengths)     # {'ashish': 6, 'priya': 5, 'rahul': 5}

# Invert dict (swap keys and values)
original = {"a": 1, "b": 2, "c": 3}
inverted = {v: k for k, v in original.items()}
print(inverted)         # {1: 'a', 2: 'b', 3: 'c'}

# Filter dict (only keep items matching condition)
scores = {"Alice": 85, "Bob": 42, "Charlie": 91, "Dave": 55}
passed = {name: score for name, score in scores.items() if score >= 60}
print(passed)           # {'Alice': 85, 'Charlie': 91}

# Transform values
upper_scores = {name.upper(): score for name, score in scores.items()}

# From two lists (zip pattern)
keys = ["name", "age", "city"]
values = ["Ashish", 28, "Delhi"]
person = {k: v for k, v in zip(keys, values)}
print(person)           # {'name': 'Ashish', 'age': 28, 'city': 'Delhi'}

# Nested: process list of dicts
employees = [
    {"id": 1, "name": "Ashish", "salary": 80000},
    {"id": 2, "name": "Priya",  "salary": 90000},
]
salary_map = {emp["id"]: emp["salary"] for emp in employees}
print(salary_map)       # {1: 80000, 2: 90000}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. SET COMPREHENSION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

# Remove duplicates + transform
words = ["apple", "banana", "apple", "cherry", "banana"]
unique_upper = {w.upper() for w in words}
print(unique_upper)     # {'APPLE', 'BANANA', 'CHERRY'}

# Find unique word lengths
lengths = {len(w) for w in words}
print(lengths)          # {5, 6}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. GENERATOR EXPRESSION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: List comprehension vs Generator expression?
A: List comp   → [] → creates ALL values in memory immediately → use when you need list
   Generator   → () → lazy, one value at a time → use for large/infinite sequences

   sum([x**2 for x in range(1_000_000)])  → allocates 1M list in RAM
   sum(x**2 for x in range(1_000_000))    → O(1) memory, processes one by one
"""

# Generator expression (parentheses, not brackets)
gen = (x ** 2 for x in range(10))
print(type(gen))        # <class 'generator'>
print(next(gen))        # 0
print(next(gen))        # 1

# Use in functions directly (no extra parens needed)
total = sum(x ** 2 for x in range(100))
maximum = max(len(word) for word in ["hi", "hello", "hey"])
any_large = any(x > 90 for x in scores.values())
all_passed = all(score >= 60 for score in scores.values())

# Memory comparison
import sys
list_comp = [x ** 2 for x in range(1000)]
gen_exp   = (x ** 2 for x in range(1000))
print(f"List size: {sys.getsizeof(list_comp)} bytes")  # ~8kB
print(f"Gen size:  {sys.getsizeof(gen_exp)} bytes")    # ~104 bytes always

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. REAL-WORLD PATTERNS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

# Pattern 1: Parse API response
api_users = [
    {"id": 1, "name": "Alice", "active": True,  "role": "admin"},
    {"id": 2, "name": "Bob",   "active": False, "role": "user"},
    {"id": 3, "name": "Carol", "active": True,  "role": "user"},
]

# Extract only active user names
active_names = [u["name"] for u in api_users if u["active"]]
print(active_names)     # ['Alice', 'Carol']

# Create lookup dict: id → user
user_lookup = {u["id"]: u for u in api_users}
print(user_lookup[1])   # {'id': 1, 'name': 'Alice', ...}

# Pattern 2: Flatten nested structure
orders = [
    {"user": "Alice", "items": ["laptop", "mouse"]},
    {"user": "Bob",   "items": ["keyboard"]},
]
all_items = [item for order in orders for item in order["items"]]
print(all_items)        # ['laptop', 'mouse', 'keyboard']

# Pattern 3: Group by (dict of lists)
from collections import defaultdict
students = [
    {"name": "Alice", "grade": "A"},
    {"name": "Bob",   "grade": "B"},
    {"name": "Carol", "grade": "A"},
]
by_grade = defaultdict(list)
for s in students:
    by_grade[s["grade"]].append(s["name"])
print(dict(by_grade))   # {'A': ['Alice', 'Carol'], 'B': ['Bob']}

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW Q&A:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: When NOT to use comprehensions?
A: When logic is complex (multiple conditions/nested transforms).
   Readability > cleverness. If it doesn't fit one line cleanly,
   use a for loop instead.

Q: Can comprehensions have side effects?
A: Technically yes but DON'T — comprehensions are for creating
   new collections, not for side effects like printing/logging.

Q: Set vs List comprehension — when to choose?
A: Set when you need unique values + O(1) lookup.
   List when order matters or duplicates needed.
"""
