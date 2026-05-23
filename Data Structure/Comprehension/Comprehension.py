"""
List comprehension is a concise and readable way to create or transform lists in Python using a single line of code.
It allows you to generate a new list by applying an expression to each item in an iterable, optionally with a condition to filter elements,
replacing the need for traditional loops.

"""

# Creating list of squres

squres = [x * x for x in range(1,5)]
print(squres)