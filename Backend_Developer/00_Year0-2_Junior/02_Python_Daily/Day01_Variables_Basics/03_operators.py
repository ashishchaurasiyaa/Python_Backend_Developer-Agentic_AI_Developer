"""
1. Arithmetic  → + - * / // % **
2. Comparison  → == != > < >= <=
3. Logical     → and or not
4. Assignment  → += -= *= /=
5. Bitwise     → & | ^ ~ << >>
6. Ternary     → x if condition else y
✅ Arithmetic  → DSA mein daily use
✅ Comparison  → conditions mein
✅ Logical     → complex conditions
✅ Assignment  → shortcut operators
✅ Ternary     → 1 line if-else
⏭️  Bitwise    → baad mein DSA mein
"""

# ================================
# ARITHMETIC OPERATORS
# ================================
a = 17
b = 5
print(f"a + b = {a + b}")
print(f"a - b = {a - b}")
print(f"a * b = {a * b}")
print(f"a / b = {a / b}")
print(f"a // b = {a // b}")
print(f"a % b = {a % b}")
print(f"a ** b = {a ** b}")

# % aur kahan use hota hai DSA mein:
#
# # Circular array mein next index
# index = (current + 1) % n
# # Last digit nikalna
# last_digit = number % 10
# # Check divisibility
# number % 3 == 0  →  3 se divisible
# # Hash function
# index = key % table_size

# Ab Comparison Operators likh

d =  40
e = 30

print(f"d == e : {d == e}") #equal
print(f"d != e : {d != e}")  # Not equal
print(f"d > e : {d > e}") # Greater than
print(f"d < e : {d < e}") # Less than
print(f"d >= e : {d >= e}") # Greater or equal
print(f"d <=e : {d <= e}") # Less or equal


# Ab Logical Operators likho:
print(f"a>10 and b>10  : {a>10 and b>10}")   # Dono true?
print(f"a>10 or b>10   : {a>10 or b>10}")    # Ek bhi true?
print(f"not a>10       : {not a>10}")


# ================================
# ASSIGNMENT OPERATORS
# ================================
x = 10
print(f"x = {x}")

x += 5      # x = x + 5
print(f"x += 5  : {x}")

x -= 3      # x = x - 3
print(f"x -= 3  : {x}")

x *= 2      # x = x * 2
print(f"x *= 2  : {x}")

x //= 3     # x = x // 3
print(f"x //= 3 : {x}")

x **= 2     # x = x ** 2
print(f"x **= 2 : {x}")

x %= 5      # x = x % 5
print(f"x %%= 5  : {x}")

# Ternary Operator
age = int(input("Enter your age: "))
if age >= 18:

    status = "Adult"
else:
    status = "Minor"

print(status)


age = 20
status = "Adult" if age >= 18 else "Minor"
print(status)