# Q1 — Calculator function
# Operations: add, subtract, multiply, divide
# calc(10, 5, "add") → 15
# calc(10, 5, "divide") → 2.0

def calc(x, y, op):
    ops = {"add": x + y, "subtract": x - y, "multiply": x * y, "divide": x / y}
    return ops[op]
print(calc(10, 5, "add"))
print(calc(10, 5, "divide"))
print(calc(10, 5, "multiply"))
print(calc(10, 5, "subtract"))

def calc(x, y, op):
    # Pehle functions define karo
    def add(x, y):      return x + y
    def subtract(x, y): return x - y
    def multiply(x, y): return x * y
    def divide(x, y):   return x / y

    ops = {"add": add, "subtract": subtract,
           "multiply": multiply, "divide": divide}

    # Phir validate karo
    if op not in ops:
        return "Invalid operation"

    return ops[op](x, y)   # function call karo

print(calc(10, 5, "add"))       # 15
print(calc(10, 5, "divide"))    # 2.0
print(calc(10, 5, "mod"))       # Invalid operation


#
# Q2 — *args se average nikalo
# average(10, 20, 30, 40) → 25.0

def average(*nums):
    return sum(nums) / len(nums)

print(average(10, 20, 30, 40))

# Q3 — **kwargs se resume print karo
# resume(name="Ashish", role="Python Dev", exp="4 years")
# Output: formatted profile

def resume(**info):
    for key, value in info.items():
        print(f"{key}: {value}")
info = {"name": "Ashish", "role": "Python Dev", "exp": "4 years"}
print(resume(**info))

# # Q4 — Lambda: sort list of dicts by age
# people = [
#     {"name": "Rahul", "age": 25},
#     {"name": "Priya", "age": 22},
#     {"name": "Amit",  "age": 28}
# ]
people = [
    {"name": "Rahul", "age": 25},
    {"name": "Priya", "age": 22},
    {"name": "Amit",  "age": 28}
]

people.sort(key=lambda x: x["age"])
for person in people:
    print(person["name"], person["age"])

# # Sort youngest to oldest using lambda
#
# # Q5 — map: Celsius list to Fahrenheit
# celsius = [0, 20, 37, 100]
# # Formula: F = C * 9/5 + 32
# # Expected: [32.0, 68.0, 98.6, 212.0]


celsius = [0, 20, 37, 100]
fahrenheit = list(map(lambda c: (c * 9/5) + 32, celsius))
print(fahrenheit)

# Q6 — filter: words longer than 4 chars
words = ["cat", "elephant", "dog", "python", "rat", "tiger"]
# Expected: ["elephant", "python", "tiger"]
long_words = list(filter(lambda w: len(w) > 4, words))
print(long_words)

# # Q7 — Recursive factorial
# # factorial(5) → 120

def factorial(n):
    if n == 0 or n == 1:   # 0! = 1 bhi hota hai!
        return 1
    return n * factorial(n-1)

print(factorial(0))
print(factorial(5))

# Q8 — Function jo check kare prime hai ya nahi
# is_prime(7) → True
# is_prime(10) → False

def is_prime(n):
    if n <= 1:
        return False
    for i in range(2, n):
        if n % i == 0:
            return False
    return True

print(is_prime(7))
print(is_prime(10))

# Q9 — Memoization (manually)
# Fibonacci with memo dict
# fib(10) → 55, but fast!

def memoize(func):
    cache = {}
    def wrapper(*args):
        if args not in cache:
            cache[args] = func(*args)
        return cache[args]
    return wrapper

@memoize
def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)

print(fib(10))

# Q10 — Decorator (simple)
# Banao ek decorator jo function se pehle/baad print kare
# "Function starting..."
# "Function done!"

def starting(func):
    def wrapper(*args, **kwargs):
        print("Function starting...")
        func(*args, **kwargs)
        print("Function done!")
    return wrapper
@starting
def my_func():
    print("Hello, world!")
my_func()


