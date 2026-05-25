"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLOSURES AND NONLOCAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ARCHITECTURE UNDERSTANDING:
  Closure = inner function that REMEMBERS variables from
            outer function's scope even after outer function returns.

  Three conditions for a closure:
  1. There must be a nested function (function inside function)
  2. Inner function must refer to a variable of outer function
  3. Outer function must return the inner function

  HOW IT WORKS:
  → Python attaches a __closure__ attribute to inner function
  → It holds "cell objects" — references to outer scope variables
  → Variables live as long as the closure lives (not just outer function)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. BASIC CLOSURE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

def outer(message):
    # 'message' is in outer's local scope
    def inner():
        print(message)     # inner "closes over" message
    return inner           # return function, not result

say_hello = outer("Hello, World!")
say_bye   = outer("Goodbye!")

say_hello()     # Hello, World!   (outer() already returned!)
say_bye()       # Goodbye!

# Prove it: __closure__ stores the captured variable
print(say_hello.__closure__)                    # (<cell at 0x...>,)
print(say_hello.__closure__[0].cell_contents)   # 'Hello, World!'

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. NONLOCAL KEYWORD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: nonlocal kab chahiye?
A: Jab inner function outer scope ki variable ko MODIFY karna chahta hai.
   Without nonlocal → read-only access.
   Without nonlocal, assignment creates a NEW local variable.
"""

def make_counter(start=0):
    count = start          # outer variable

    def increment(step=1):
        nonlocal count     # tell Python: modify outer 'count', don't create new local
        count += step
        return count

    def reset():
        nonlocal count
        count = start

    def get():
        return count       # read-only: no nonlocal needed

    return increment, reset, get

inc, reset, get = make_counter(0)
print(inc())        # 1
print(inc())        # 2
print(inc(5))       # 7
print(get())        # 7
reset()
print(get())        # 0

# Without nonlocal — this would fail:
def broken_counter():
    count = 0
    def increment():
        count += 1     # UnboundLocalError: Python sees 'count =' as local variable
    return increment

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. CLOSURE AS FACTORY FUNCTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
Factory pattern: function that creates customized functions.
Very common in decorators and configuration.
"""

def make_multiplier(factor):
    """Returns a function that multiplies by factor."""
    def multiply(x):
        return x * factor   # closes over 'factor'
    return multiply

double  = make_multiplier(2)
triple  = make_multiplier(3)
by_ten  = make_multiplier(10)

print(double(5))    # 10
print(triple(5))    # 15
print(by_ten(5))    # 50

# Real use: discount calculator factory
def make_discount(percent):
    rate = percent / 100
    def apply(price):
        return price * (1 - rate)
    return apply

student_discount = make_discount(20)
employee_discount = make_discount(30)

print(student_discount(1000))   # 800.0
print(employee_discount(1000))  # 700.0

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. CLOSURES IN LOOPS — CLASSIC GOTCHA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
INTERVIEW Q: Classic closure bug in loops.
All closures capture the SAME variable (last value after loop ends).
"""

# BUG version
functions = []
for i in range(3):
    def f():
        return i           # captures 'i' by reference, not by value!
    functions.append(f)

print([f() for f in functions])   # [2, 2, 2] — NOT [0, 1, 2] !!

# FIX 1: default argument captures value at creation time
functions = []
for i in range(3):
    def f(x=i):            # x=i evaluated NOW, not later
        return x
    functions.append(f)

print([f() for f in functions])   # [0, 1, 2] ✓

# FIX 2: factory function
def make_fn(x):
    def f():
        return x
    return f

functions = [make_fn(i) for i in range(3)]
print([f() for f in functions])   # [0, 1, 2] ✓

# ━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. REAL-WORLD PATTERNS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━

# Pattern 1: Memoization using closure
def memoize(func):
    cache = {}                      # closure variable — persists across calls
    def wrapper(*args):
        if args not in cache:
            cache[args] = func(*args)
        return cache[args]
    wrapper.cache = cache           # expose cache for debugging
    return wrapper

@memoize
def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

print(fibonacci(35))    # Fast — cached!
print(fibonacci.cache)  # See all cached values

# Pattern 2: Configurable validator
def make_validator(min_val, max_val):
    def validate(value):
        if not (min_val <= value <= max_val):
            raise ValueError(f"Value {value} must be between {min_val} and {max_val}")
        return value
    return validate

validate_age    = make_validator(0, 120)
validate_score  = make_validator(0, 100)
validate_port   = make_validator(1024, 65535)

print(validate_age(25))     # 25
print(validate_score(95))   # 95

# Pattern 3: Event handler factory
def make_handler(event_name, logger):
    def handler(data):
        logger(f"[{event_name}] Received: {data}")
        # process data...
    return handler

import logging
log = logging.getLogger(__name__)
on_login  = make_handler("USER_LOGIN",  print)
on_logout = make_handler("USER_LOGOUT", print)

on_login({"user_id": 42})   # [USER_LOGIN] Received: {'user_id': 42}

# Pattern 4: Partial application (before functools.partial existed)
def multiply(x, y):
    return x * y

def partial_apply(func, *bound_args):
    def wrapper(*args):
        return func(*bound_args, *args)
    return wrapper

double = partial_apply(multiply, 2)
print(double(5))    # 10

"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INTERVIEW Q&A:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q: Closure kya hai simple words mein?
A: Inner function jo outer function ke variable ko yaad rakhti hai
   outer function return ho jaane ke baad bhi.

Q: Decorator aur closure ka kya relation hai?
A: Har decorator ek closure hai. Decorator mein wrapper function
   'func' variable ko close karta hai aur use karta hai.

Q: global vs nonlocal?
A: global   → module-level variable modify karna
   nonlocal → immediately enclosing scope variable modify karna
   Dono se avoid karo jab possible — makes code hard to reason about.

Q: When to use closures over classes?
A: Closure: simple state + 1-2 behaviors (counter, cache, validator)
   Class:   complex state + many methods (when grows beyond 2 behaviors)
   Rule: start with closure, graduate to class when needed.
"""
